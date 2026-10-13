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


class ArticleQuerySet(models.QuerySet):
    def published(self):
        return self.filter(status=Article.Status.PUBLISHED)


class Article(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"

    category = models.CharField("category", max_length=2, choices=Category.choices,
                                default=Category.PROBLEM, db_index=True)
    title = models.CharField("title", max_length=200)
    slug = models.SlugField("slug", max_length=220, unique=True)
    summary = models.CharField("summary", max_length=280, blank=True)
    body = models.TextField("body")

    status = models.CharField("status", max_length=16, choices=Status.choices,
                              default=Status.PUBLISHED, db_index=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="articles",
    )
    tags = models.CharField("tags", max_length=180, blank=True,
                            help_text="Separate with commas.")

    views = models.PositiveIntegerField("views", default=0)
    helpful = models.PositiveIntegerField("helpful", default=0)
    not_helpful = models.PositiveIntegerField("not helpful", default=0)

    objects = ArticleQuerySet.as_manager()

    class Meta:
        verbose_name = "solution article"
        verbose_name_plural = "solution articles"
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
    def category_label(self):
        return dict(Category.choices).get(self.category, self.category)

    @property
    def category_badge(self):
        return "badge--danger" if self.category == Category.PROBLEM else "badge--teal"

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
