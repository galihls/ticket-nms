from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.core.models import ActivityLog
from apps.tickets.models import Ticket

from .models import Article, Category


class ArticleForm(forms.ModelForm):
    class Meta:
        model = Article
        fields = ["category", "title", "summary", "body", "tags", "status"]
        widgets = {
            "title": forms.TextInput(attrs={
                "class": "form-input",
                "placeholder": "e.g. Resolving link down due to fiber cut",
            }),
            "summary": forms.TextInput(attrs={
                "class": "form-input",
                "placeholder": "One sentence: what does this article solve?",
            }),
            "body": forms.Textarea(attrs={
                "class": "form-textarea", "rows": 16,
                "placeholder": "Symptoms\n\nTroubleshooting steps\n\nResolution\n\n"
                               "Separate paragraphs with a blank line.",
            }),
            "tags": forms.TextInput(attrs={
                "class": "form-input", "placeholder": "fiber, link-down, olt",
            }),
            "category": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["summary"].required = False


@login_required
def solution_home(request):
    """Beranda knowledge base: dua kategori + artikel populer."""
    q = request.GET.get("q", "").strip()
    if q:
        return redirect(f"{reverse('solutions:browse')}?q={q}")

    categories = []
    for value, label in Category.choices:
        count = Article.objects.published().filter(category=value).count()
        categories.append({
            "value": value,
            "label": label,
            "count": count,
            "badge": "badge--danger" if value == Category.PROBLEM else "badge--teal",
        })

    return render(request, "solutions/home.html", {
        "page_title": "Solutions",
        "breadcrumb": [("Solutions", None)],
        "categories": categories,
        "popular": Article.objects.published().order_by("-views")[:6],
        "recent": Article.objects.published().select_related("author")[:6],
        "total": Article.objects.published().count(),
    })


@login_required
def browse(request):
    """Daftar artikel dengan filter kategori/pencarian."""
    qs = Article.objects.select_related("author")
    category = request.GET.get("kategori", "")
    q = request.GET.get("q", "").strip()
    sort = request.GET.get("sort", "-updated_at")

    if not (request.user.is_staff or request.user.is_superuser):
        qs = qs.published()

    if category in dict(Category.choices):
        qs = qs.filter(category=category)
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(body__icontains=q)
                       | Q(tags__icontains=q) | Q(summary__icontains=q))

    if sort not in ("-updated_at", "-views", "title", "-helpful"):
        sort = "-updated_at"
    qs = qs.order_by(sort)

    page = Paginator(qs, 12).get_page(request.GET.get("page"))
    
    category_label = dict(Category.choices).get(category)

    return render(request, "solutions/browse.html", {
        "page_title": category_label if category_label else "Browse Solutions",
        "breadcrumb": [("Solutions", reverse("solutions:home")),
                       (category_label if category_label else "Browse", None)],
        "page_obj": page,
        "categories": Category.choices,
        "selected": {"kategori": category, "q": q, "sort": sort},
        "sorts": [("-updated_at", "Latest"), ("-views", "Most Viewed"),
                  ("-helpful", "Most Helpful"), ("title", "Title A–Z")],
    })


@login_required
def article_detail(request, slug):
    article = get_object_or_404(
        Article.objects.select_related("author"), slug=slug)

    # Protect draft articles: only author or staff can view drafts
    if article.status != Article.Status.PUBLISHED:
        if article.author != request.user and not (request.user.is_staff or request.user.is_superuser):
            from django.http import Http404
            raise Http404("Article not found.")

    can_edit = (article.author == request.user) or request.user.is_staff or request.user.is_superuser

    seen = request.session.setdefault("articles_seen", [])
    if article.pk not in seen:
        Article.objects.filter(pk=article.pk).update(views=article.views + 1)
        article.views += 1
        seen.append(article.pk)
        request.session.modified = True

    related = (Article.objects.published()
               .filter(category=article.category).exclude(pk=article.pk)[:4])

    return render(request, "solutions/detail.html", {
        "page_title": article.title,
        "breadcrumb": [("Solutions", reverse("solutions:home")),
                       (article.category_label, reverse("solutions:browse") + f"?kategori={article.category}"),
                       (article.title, None)],
        "article": article,
        "can_edit": can_edit,
        "related": related,
        "voted": article.pk in request.session.get("articles_voted", []),
    })


@login_required
def article_create(request):
    initial = {}
    source_ticket = None

    # Dipanggil dari tombol "jadikan artikel" saat menutup tiket
    number = request.GET.get("dari")
    if number:
        source_ticket = Ticket.objects.filter(number=number).first()
        if source_ticket:
            category = (Category.PROBLEM
                        if source_ticket.ticket_type == Ticket.Type.PROBLEM
                        else Category.FEATURE)
            initial = {
                "title": source_ticket.subject,
                "summary": f"Solution from ticket {source_ticket.number}.",
                "body": (f"{source_ticket.description}\n\n"
                         f"Resolution\n\n{source_ticket.close_reason}"),
                "tags": source_ticket.tags,
                "category": category,
            }

    form = ArticleForm(request.POST or None, initial=initial)

    if request.method == "POST" and form.is_valid():
        article = form.save(commit=False)
        article.author = request.user
        article.save()

        ActivityLog.record(
            request.user, ActivityLog.Verb.ARTICLE_CREATE,
            target_label=article.category_label,
            subject=article.title, status=article.get_status_display(),
            pic=request.user.display_name, url=article.get_absolute_url(),
        )
        messages.success(request, "Solution article saved.")
        return redirect(article)

    if request.method == "POST":
        messages.error(request, "Please review the highlighted fields.")

    return render(request, "solutions/form.html", {
        "page_title": "Create Solution Article",
        "breadcrumb": [("Solutions", reverse("solutions:home")), ("New Article", None)],
        "form": form,
        "source_ticket": source_ticket,
        "is_edit": False,
    })


@login_required
def article_edit(request, slug):
    article = get_object_or_404(Article, slug=slug)

    # Broken Object Level Authorization (IDOR) check
    if article.author != request.user and not (request.user.is_staff or request.user.is_superuser):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("You do not have permission to edit this article.")

    form = ArticleForm(request.POST or None, instance=article)

    if request.method == "POST" and form.is_valid():
        form.save()
        ActivityLog.record(
            request.user, ActivityLog.Verb.ARTICLE_CREATE,
            target_label=article.category_label,
            subject=f"Updated: {article.title}", status=article.get_status_display(),
            pic=request.user.display_name, url=article.get_absolute_url(),
        )
        messages.success(request, "Article updated.")
        return redirect(article)

    return render(request, "solutions/form.html", {
        "page_title": f"Edit: {article.title}",
        "breadcrumb": [("Solutions", reverse("solutions:home")),
                       (article.title, article.get_absolute_url()), ("Edit", None)],
        "form": form,
        "article": article,
        "is_edit": True,
    })


@login_required
@require_POST
def article_vote(request, slug):
    article = get_object_or_404(Article, slug=slug)
    voted = request.session.setdefault("articles_voted", [])

    if article.pk in voted:
        messages.info(request, "You have already voted on this article.")
        return redirect(article)

    if request.POST.get("vote") == "yes":
        Article.objects.filter(pk=article.pk).update(helpful=article.helpful + 1)
        messages.success(request, "Thank you for your feedback.")
    else:
        Article.objects.filter(pk=article.pk).update(not_helpful=article.not_helpful + 1)
        messages.success(request, "Feedback recorded — article will be reviewed.")

    voted.append(article.pk)
    request.session.modified = True
    return redirect(article)
