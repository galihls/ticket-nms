from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from apps.core.models import ActivityLog
from apps.core.views import admin_required
from apps.tickets.models import Ticket

from .forms import LoginForm, ProfileForm
from .models import User
from .rate_limit import clear_failed_logins, is_locked_out, record_failed_login


class LoginView(auth_views.LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def dispatch(self, request, *args, **kwargs):
        if request.method == "POST":
            username = request.POST.get("username", "").strip()
            locked, error_msg = is_locked_out(request, username)
            if locked:
                messages.error(request, error_msg)
                form = self.get_form()
                return self.render_to_response(self.get_context_data(form=form))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["sso"] = settings.SSO
        return context

    def form_valid(self, form):
        username = form.cleaned_data.get("username")
        clear_failed_logins(self.request, username)
        response = super().form_valid(form)
        _record_login(self.request, method="Local account")
        return response

    def form_invalid(self, form):
        username = self.request.POST.get("username", "").strip()
        record_failed_login(self.request, username)
        return super().form_invalid(form)


class LogoutView(auth_views.LogoutView):
    next_page = reverse_lazy("accounts:login")


def sso_login(request):
    """Masuk lewat Office 365."""
    if request.user.is_authenticated:
        return redirect("core:dashboard")

    # Strictly block SSO bypass if not explicitly enabled, not in demo mode, or in production
    if not settings.SSO.get("ENABLED", False) or not settings.SSO.get("DEMO_MODE", False) or not settings.DEBUG:
        messages.warning(
            request,
            "Office 365 SSO is not configured yet. Please contact the system administrator.",
        )
        return redirect("accounts:login")

    user = User.objects.filter(username=settings.SSO.get("DEMO_USERNAME")).first()
    if user is None:
        messages.error(request, "SSO demo user account not found.")
        return redirect("accounts:login")

    auth_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    _record_login(request, method=f"SSO {settings.SSO['PROVIDER']}")
    return redirect("core:dashboard")


def _record_login(request, method):
    user = request.user
    messages.success(request, f"Welcome back, {user.display_name}.")
    ActivityLog.record(
        user, ActivityLog.Verb.LOGIN,
        target_label=user.username,
        subject=f"Signed in via {method}",
        status="Active", pic=user.display_name,
    )


@login_required
def profile(request):
    """Profil agent — identitas sesi yang sedang dipakai + ringkasan kerjanya."""
    form = ProfileForm(request.POST or None, instance=request.user)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profile updated.")
        return redirect("accounts:profile")

    stats = Ticket.objects.filter(assignee=request.user).aggregate(
        total=Count("id"),
        open=Count("id", filter=Q(status=Ticket.Status.OPEN)),
        outstanding=Count("id", filter=Q(status=Ticket.Status.OUTSTANDING)),
        closed=Count("id", filter=Q(status=Ticket.Status.CLOSED)),
    )

    return render(request, "accounts/profile.html", {
        "page_title": "My Profile",
        "breadcrumb": [("My Profile", None)],
        "form": form,
        "stats": stats,
        "sso": settings.SSO,
        "recent": Ticket.objects.filter(assignee=request.user)[:6],
        "activities": ActivityLog.objects.filter(actor=request.user)[:8],
    })


@admin_required
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
        "page_title": "Agents",
        "breadcrumb": [("Agents", None)],
        "agents": agents,
    })
