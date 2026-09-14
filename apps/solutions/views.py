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

from .models import Article, Category, Folder


class ArticleForm(forms.ModelForm):
    class Meta:
        model = Article
        fields = ["folder", "title", "summary", "body", "tags", "status"]
        widgets = {
            "title": forms.TextInput(attrs={
                "class": "form-input",
                "placeholder": "mis. Mengatasi link down akibat putus fiber",
            }),
            "summary": forms.TextInput(attrs={
                "class": "form-input",
                "placeholder": "Satu kalimat: artikel ini menjawab apa?",
            }),
            "body": forms.Textarea(attrs={
                "class": "form-textarea", "rows": 16,
                "placeholder": "Gejala\n\nLangkah troubleshooting\n\nSolusi\n\n"
                               "Pisahkan paragraf dengan satu baris kosong.",
            }),
            "tags": forms.TextInput(attrs={
                "class": "form-input", "placeholder": "fiber, link-down, olt",
            }),
            "folder": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["folder"].queryset = Folder.objects.all()
        self.fields["summary"].required = False


@login_required
def solution_home(request):
    """Beranda knowledge base: dua kategori + folder + artikel populer."""
    q = request.GET.get("q", "").strip()
    if q:
        return redirect(f"{reverse('solutions:browse')}?q={q}")

    categories = []
    for value, label in Category.choices:
        folders = (Folder.objects.filter(category=value)
                   .annotate(n=Count("articles",
                                     filter=Q(articles__status=Article.Status.PUBLISHED))))
        categories.append({
            "value": value,
            "label": label,
            "folders": folders,
            "count": sum(f.n for f in folders),
            "badge": "badge--danger" if value == Category.PROBLEM else "badge--teal",
        })

    return render(request, "solutions/home.html", {
        "page_title": "Solutions",
        "breadcrumb": [("Solutions", None)],
        "categories": categories,
        "popular": Article.objects.published().select_related("folder")
                                  .order_by("-views")[:6],
        "recent": Article.objects.published().select_related("folder", "author")[:6],
        "total": Article.objects.published().count(),
    })


@login_required
def browse(request):
    """Daftar artikel dengan filter kategori/folder/pencarian."""
    qs = Article.objects.select_related("folder", "author")
    category = request.GET.get("kategori", "")
    folder_slug = request.GET.get("folder", "")
    q = request.GET.get("q", "").strip()
    sort = request.GET.get("sort", "-updated_at")

    if not (request.user.is_staff or request.user.is_superuser):
        qs = qs.published()

    if category in dict(Category.choices):
        qs = qs.filter(folder__category=category)
    folder = None
    if folder_slug:
        folder = get_object_or_404(Folder, slug=folder_slug)
        qs = qs.filter(folder=folder)
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(body__icontains=q)
                       | Q(tags__icontains=q) | Q(summary__icontains=q))

    if sort not in ("-updated_at", "-views", "title", "-helpful"):
        sort = "-updated_at"
    qs = qs.order_by(sort)

    page = Paginator(qs, 12).get_page(request.GET.get("page"))

    return render(request, "solutions/browse.html", {
        "page_title": folder.name if folder else "Jelajahi Solusi",
        "breadcrumb": [("Solutions", reverse("solutions:home")),
                       (folder.name if folder else "Jelajahi", None)],
        "page_obj": page,
        "categories": Category.choices,
        "folders": Folder.objects.all(),
        "selected": {"kategori": category, "folder": folder_slug, "q": q, "sort": sort},
        "folder": folder,
        "sorts": [("-updated_at", "Terbaru"), ("-views", "Paling dilihat"),
                  ("-helpful", "Paling membantu"), ("title", "Judul A–Z")],
    })


@login_required
def article_detail(request, slug):
    article = get_object_or_404(
        Article.objects.select_related("folder", "author"), slug=slug)

    # Penghitung dilihat: cukup satu kali per sesi supaya angkanya tidak
    # melonjak hanya karena agent me-refresh halaman.
    seen = request.session.setdefault("articles_seen", [])
    if article.pk not in seen:
        Article.objects.filter(pk=article.pk).update(views=article.views + 1)
        article.views += 1
        seen.append(article.pk)
        request.session.modified = True

    related = (Article.objects.published()
               .filter(folder=article.folder).exclude(pk=article.pk)[:4])

    return render(request, "solutions/detail.html", {
        "page_title": article.title,
        "breadcrumb": [("Solutions", reverse("solutions:home")),
                       (article.folder.name, article.folder.get_absolute_url()),
                       (article.title, None)],
        "article": article,
        "related": related,
        "voted": article.pk in request.session.get("articles_voted", []),
    })


@login_required
def folder_detail(request, slug):
    folder = get_object_or_404(Folder, slug=slug)
    return redirect(f"{reverse('solutions:browse')}?folder={folder.slug}")


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
                "summary": f"Solusi dari tiket {source_ticket.number}.",
                "body": (f"{source_ticket.description}\n\n"
                         f"Penyelesaian\n\n{source_ticket.close_reason}"),
                "tags": source_ticket.tags,
                "folder": Folder.objects.filter(category=category).first(),
            }

    form = ArticleForm(request.POST or None, initial=initial)

    if request.method == "POST" and form.is_valid():
        article = form.save(commit=False)
        article.author = request.user
        article.save()

        ActivityLog.record(
            request.user, ActivityLog.Verb.ARTICLE_CREATE,
            target_label=article.folder.get_category_display(),
            subject=article.title, status=article.get_status_display(),
            pic=request.user.display_name, url=article.get_absolute_url(),
        )
        messages.success(request, "Artikel solusi tersimpan.")
        return redirect(article)

    if request.method == "POST":
        messages.error(request, "Periksa kembali isian yang ditandai merah.")

    return render(request, "solutions/form.html", {
        "page_title": "Buat Artikel Solusi",
        "breadcrumb": [("Solutions", reverse("solutions:home")), ("Artikel Baru", None)],
        "form": form,
        "source_ticket": source_ticket,
        "is_edit": False,
    })


@login_required
def article_edit(request, slug):
    article = get_object_or_404(Article, slug=slug)
    form = ArticleForm(request.POST or None, instance=article)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Artikel diperbarui.")
        return redirect(article)

    return render(request, "solutions/form.html", {
        "page_title": f"Ubah: {article.title}",
        "breadcrumb": [("Solutions", reverse("solutions:home")),
                       (article.title, article.get_absolute_url()), ("Ubah", None)],
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
        messages.info(request, "Anda sudah menilai artikel ini.")
        return redirect(article)

    if request.POST.get("vote") == "yes":
        Article.objects.filter(pk=article.pk).update(helpful=article.helpful + 1)
        messages.success(request, "Terima kasih atas masukannya.")
    else:
        Article.objects.filter(pk=article.pk).update(not_helpful=article.not_helpful + 1)
        messages.success(request, "Masukan tercatat — artikel akan ditinjau ulang.")

    voted.append(article.pk)
    request.session.modified = True
    return redirect(article)
