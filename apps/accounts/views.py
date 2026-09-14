from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from apps.core.models import ActivityLog
from apps.tickets.models import Ticket

from .forms import LoginForm, ProfileForm
from .models import User


class LoginView(auth_views.LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["sso"] = settings.SSO
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        _record_login(self.request, method="Akun lokal")
        return response


class LogoutView(auth_views.LogoutView):
    next_page = reverse_lazy("accounts:login")


def sso_login(request):
    """Masuk lewat Office 365.

    Integrasi SAML 2.0 / OIDC sungguhan menunggu app registration dari tim IT
    INITECH. Selama `SSO.DEMO_MODE` aktif, endpoint ini memetakan langsung ke
    satu akun agent supaya alur login dapat diperagakan utuh; begitu tenant
    siap, hanya fungsi ini yang diganti — tampilan dan sisa aplikasi tetap.
    """
    if request.user.is_authenticated:
        return redirect("core:dashboard")

    if not settings.SSO["DEMO_MODE"]:
        messages.warning(
            request,
            "SSO Office 365 belum dikonfigurasi. Hubungi administrator sistem.",
        )
        return redirect("accounts:login")

    user = (User.objects.filter(username=settings.SSO["DEMO_USERNAME"]).first()
            or User.objects.filter(is_superuser=True).first()
            or User.objects.filter(is_active=True).first())

    if user is None:
        messages.error(request, "Belum ada akun pengguna. Jalankan seed data demo.")
        return redirect("accounts:login")

    auth_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    _record_login(request, method=f"SSO {settings.SSO['PROVIDER']}")
    return redirect("core:dashboard")


def _record_login(request, method):
    user = request.user
    messages.success(request, f"Selamat datang, {user.display_name}.")
    ActivityLog.record(
        user, ActivityLog.Verb.LOGIN,
        target_label=user.username,
        subject=f"Masuk via {method}",
        status="Aktif", pic=user.display_name,
    )


@login_required
def profile(request):
    """Profil agent — identitas sesi yang sedang dipakai + ringkasan kerjanya."""
    form = ProfileForm(request.POST or None, instance=request.user)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profil diperbarui.")
        return redirect("accounts:profile")

    stats = Ticket.objects.filter(assignee=request.user).aggregate(
        total=Count("id"),
        open=Count("id", filter=Q(status=Ticket.Status.OPEN)),
        outstanding=Count("id", filter=Q(status=Ticket.Status.OUTSTANDING)),
        closed=Count("id", filter=Q(status=Ticket.Status.CLOSED)),
    )

    return render(request, "accounts/profile.html", {
        "page_title": "Profil Saya",
        "breadcrumb": [("Profil Saya", None)],
        "form": form,
        "stats": stats,
        "sso": settings.SSO,
        "recent": Ticket.objects.filter(assignee=request.user)[:6],
        "activities": ActivityLog.objects.filter(actor=request.user)[:8],
    })


@login_required
def agent_list(request):
    """Daftar agent + beban kerjanya — dipakai supervisor saat membagi tiket."""
    agents = (User.objects.filter(is_active=True)
              .annotate(
                  total=Count("tickets_assigned"),
                  open=Count("tickets_assigned",
                             filter=Q(tickets_assigned__status=Ticket.Status.OPEN)),
                  outstanding=Count("tickets_assigned",
                                    filter=Q(tickets_assigned__status=Ticket.Status.OUTSTANDING)),
                  closed=Count("tickets_assigned",
                               filter=Q(tickets_assigned__status=Ticket.Status.CLOSED)),
              ))
    return render(request, "accounts/agents.html", {
        "page_title": "Agent",
        "breadcrumb": [("Agent", None)],
        "agents": agents,
    })
