from django import forms
from django.utils import timezone

from apps.accounts.models import User

from .models import Ticket, TicketReply

GROUPS = [
    ("NOC", "NOC"),
    ("Field Engineer", "Field Engineer"),
    ("Network Engineer", "Network Engineer"),
    ("Helpdesk", "Helpdesk"),
    ("Product", "Product"),
]


class TicketForm(forms.ModelForm):
    """Form buat & ubah tiket.

    Nomor tiket tidak ada di form: dihasilkan otomatis saat simpan supaya
    tidak mungkin bentrok kalau dua agent membuat tiket bersamaan.
    """

    group = forms.ChoiceField(label="Grup penanganan", choices=GROUPS, required=False)

    class Meta:
        model = Ticket
        fields = [
            "ticket_type", "subject", "description", "priority", "status", "source",
            "requester_name", "requester_email", "company", "site_code",
            "assignee", "group", "opened_at", "due_at", "tags",
        ]
        widgets = {
            "ticket_type": forms.RadioSelect(),
            "subject": forms.TextInput(attrs={
                "placeholder": "Ringkas dan spesifik, mis. Link down site CKGK0",
            }),
            "description": forms.Textarea(attrs={
                "rows": 7,
                "placeholder": "Jelaskan gejala, waktu kejadian, dan langkah yang sudah dicoba…",
            }),
            "requester_name": forms.TextInput(attrs={"placeholder": "Nama pelapor"}),
            "requester_email": forms.EmailInput(attrs={"placeholder": "nama@initech.co.id"}),
            "company": forms.TextInput(attrs={"placeholder": "Unit / perusahaan pelapor"}),
            "site_code": forms.TextInput(attrs={"placeholder": "mis. CKGK0"}),
            "tags": forms.TextInput(attrs={"placeholder": "link-down, fiber, prioritas"}),
            "opened_at": forms.DateTimeInput(attrs={"type": "datetime-local"},
                                             format="%Y-%m-%dT%H:%M"),
            "due_at": forms.DateTimeInput(attrs={"type": "datetime-local"},
                                          format="%Y-%m-%dT%H:%M"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["assignee"].queryset = User.objects.filter(is_active=True)
        self.fields["assignee"].label = "Person In Charge"
        self.fields["assignee"].empty_label = "— Belum ditugaskan —"
        self.fields["requester_email"].required = False

        if not self.instance.pk:
            self.fields["opened_at"].initial = timezone.localtime().replace(
                second=0, microsecond=0)

        # Kelas CSS dipasang di sini, bukan di template, supaya satu form bisa
        # dipakai ulang di halaman buat maupun ubah tanpa duplikasi markup.
        for name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.RadioSelect):
                continue
            if isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "form-select")
            elif isinstance(widget, forms.Textarea):
                widget.attrs.setdefault("class", "form-textarea")
            else:
                widget.attrs.setdefault("class", "form-input")

    def clean(self):
        data = super().clean()
        opened_at, due_at = data.get("opened_at"), data.get("due_at")
        if opened_at and due_at and due_at < opened_at:
            self.add_error("due_at", "Target selesai tidak boleh sebelum waktu open.")
        return data


class ReplyForm(forms.ModelForm):
    class Meta:
        model = TicketReply
        fields = ["body", "is_private"]
        widgets = {
            "body": forms.Textarea(attrs={
                "class": "form-textarea", "rows": 4,
                "placeholder": "Tulis balasan untuk pelapor…",
            }),
        }
        labels = {"body": "Balasan"}


class CloseTicketForm(forms.Form):
    """Menutup tiket wajib disertai alasan — itu yang masuk ke audit trail."""

    REASONS = [
        ("Perbaikan selesai", "Perbaikan selesai"),
        ("Tidak dapat direproduksi", "Tidak dapat direproduksi"),
        ("Duplikat tiket lain", "Duplikat tiket lain"),
        ("Permintaan ditolak", "Permintaan ditolak"),
        ("Selesai oleh pelapor", "Selesai oleh pelapor"),
        ("Lainnya", "Lainnya"),
    ]

    reason_category = forms.ChoiceField(
        label="Kategori alasan", choices=REASONS,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    reason = forms.CharField(
        label="Keterangan close", widget=forms.Textarea(attrs={
            "class": "form-textarea", "rows": 3,
            "placeholder": "Akar masalah dan tindakan yang dilakukan…",
        }),
    )
    create_article = forms.BooleanField(
        label="Jadikan bahan artikel solusi", required=False,
        help_text="Membuka form artikel setelah tiket ditutup.",
    )
