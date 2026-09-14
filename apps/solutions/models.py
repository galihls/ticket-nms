"""Knowledge base — panduan troubleshooting hasil penanganan agent."""

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

from apps.core.models import TimeStampedModel


class Category(models.TextChoices):
    """Dua kategori artikel sesuai kebutuhan: Problem & Feature Request."""

    PROBLEM = "PR", "Problem"
    FEATURE = "FR", "Feature Request"


class Folder(TimeStampedModel):
    """Pengelompokan artikel di dalam sebuah kategori."""

    category = models.CharField("kategori", max_length=2, choices=Category.choices,
                                db_index=True)
    name = models.CharField("nama folder", max_length=120)
    slug = models.SlugField("slug", max_length=140, unique=True)
    description = models.CharField("deskripsi", max_length=255, blank=True)
    icon = models.CharField("ikon", max_length=32, default="book",
                            help_text="Nama ikon pada set SVG internal.")
    order = models.PositiveIntegerField("urutan", default=0)

    class Meta:
        verbose_name = "folder solusi"
        verbose_name_plural = "folder solusi"
        ordering = ["category", "order", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:140]
        return super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("solutions:folder", args=[self.slug])


class ArticleQuerySet(models.QuerySet):
    def published(self):
        return self.filter(status=Article.Status.PUBLISHED)


class Article(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draf"
        PUBLISHED = "published", "Terbit"

    folder = models.ForeignKey(Folder, on_delete=models.PROTECT, related_name="articles")
    title = models.CharField("judul", max_length=200)
    slug = models.SlugField("slug", max_length=220, unique=True)
    summary = models.CharField("ringkasan", max_length=280, blank=True)
    body = models.TextField("isi artikel")

    status = models.CharField("status", max_length=16, choices=Status.choices,
                              default=Status.PUBLISHED, db_index=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="articles",
    )
    tags = models.CharField("tag", max_length=180, blank=True,
                            help_text="Pisahkan dengan koma.")

    views = models.PositiveIntegerField("dilihat", default=0)
    helpful = models.PositiveIntegerField("membantu", default=0)
    not_helpful = models.PositiveIntegerField("tidak membantu", default=0)

    objects = ArticleQuerySet.as_manager()

    class Meta:
        verbose_name = "artikel solusi"
        verbose_name_plural = "artikel solusi"
        ordering = ["-updated_at", "-id"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)[:200] or "artikel"
            slug, n = base, 2
            while Article.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{n}"
                n += 1
            self.slug = slug
        return super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("solutions:detail", args=[self.slug])

    @property
    def category(self):
        return self.folder.category

    @property
    def category_label(self):
        return Category(self.folder.category).label

    @property
    def category_badge(self):
        return "badge--danger" if self.folder.category == Category.PROBLEM else "badge--teal"

    @property
    def tag_list(self):
        return [t.strip() for t in self.tags.split(",") if t.strip()]

    @property
    def paragraphs(self):
        """Isi artikel dipecah per paragraf — editor kaya menyusul."""
        return [p.strip() for p in self.body.split("\n\n") if p.strip()]

    @property
    def helpful_percent(self):
        total = self.helpful + self.not_helpful
        return round(self.helpful * 100 / total) if total else 0
