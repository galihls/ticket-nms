from django import forms
from django.utils import timezone

from apps.accounts.models import User

from .models import Ticket, TicketReply, Company

GROUPS = [
    ("NOC", "NOC"),
    ("Field Engineer", "Field Engineer"),
    ("Network Engineer", "Network Engineer"),
    ("Helpdesk", "Helpdesk"),
    ("Product", "Product"),
]


class CompanyForm(forms.ModelForm):
    """Form to create and edit corporate clients."""

    class Meta:
        model = Company
        fields = ["name", "code", "contact_person", "contact_phone", "address", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. PT Telekomunikasi Indonesia"}),
            "code": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. TELKOM"}),
            "contact_person": forms.TextInput(attrs={"class": "form-input", "placeholder": "PIC Name"}),
            "contact_phone": forms.TextInput(attrs={"class": "form-input", "placeholder": "08xxxxxxxxxx"}),
            "address": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Office address..."}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check"}),
        }


class TicketForm(forms.ModelForm):
    """Form to create and edit tickets."""

    company = forms.ChoiceField(
        label="Company / Unit",
        choices=[],
        widget=forms.Select(attrs={"class": "form-select"}),
        required=True,
    )

    class Meta:
        model = Ticket
        fields = [
            "ticket_type", "subject", "description", "address", "problem_category", "problem_detail",
            "priority", "status", "source", "company", "tags", "requester_phone"
        ]
        widgets = {
            "ticket_type": forms.RadioSelect(),
            "subject": forms.TextInput(attrs={
                "placeholder": "Concise and specific, e.g. Link down site CKGK0",
            }),
            "description": forms.Textarea(attrs={
                "rows": 7,
                "placeholder": "Explain symptoms, time of incident, and troubleshooting steps already attempted…",
            }),
            "address": forms.Textarea(attrs={
                "rows": 3,
                "placeholder": "Incident location address / origin relocation address…",
            }),
            "requester_phone": forms.TextInput(attrs={"placeholder": "08xxxxxxxxx"}),
            "tags": forms.TextInput(attrs={"placeholder": "link-down, fiber, urgent"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Dynamic company choices from Company table
        company_choices = [("", "Select company...")]
        try:
            db_companies = list(Company.objects.filter(is_active=True).order_by("name").values_list("name", "name"))
            if not db_companies:
                db_companies = [(c, c) for c in Ticket.DEFAULT_COMPANIES]
            company_choices.extend(db_companies)
        except Exception:
            company_choices.extend([(c, c) for c in Ticket.DEFAULT_COMPANIES])

        if self.instance and getattr(self.instance, "company", None):
            val = self.instance.company
            if not any(c[0] == val for c in company_choices):
                company_choices.append((val, val))

        self.fields["company"].choices = company_choices
        self.fields["company"].widget.choices = company_choices

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
            
        ticket_type = data.get("ticket_type")
        problem_category = data.get("problem_category")
        problem_detail = data.get("problem_detail")
        address = data.get("address")
        priority = data.get("priority")

        if ticket_type == Ticket.Type.PROBLEM:
            if not problem_category:
                self.add_error("problem_category", "Problem category is required for Problem tickets.")
            if problem_category == Ticket.ProblemCategory.OTHER and not problem_detail:
                self.add_error("problem_detail", "Category detail is required when selecting Other.")
        elif ticket_type == Ticket.Type.FEATURE:
            if priority not in (Ticket.Priority.MEDIUM, Ticket.Priority.HIGH):
                self.add_error("priority", "Feature Request only allows Level Medium or High.")
        elif ticket_type == Ticket.Type.RELOCATION:
            if not address:
                self.add_error("address", "Address is required for Relocation tickets.")
            if priority != Ticket.Priority.MEDIUM:
                self.add_error("priority", "Relocation tickets can only have Level Medium.")
                
        return data


class ReplyForm(forms.ModelForm):
    class Meta:
        model = TicketReply
        fields = ["body", "is_private"]
        widgets = {
            "body": forms.Textarea(attrs={
                "class": "form-textarea", "rows": 4,
                "placeholder": "Write an internal note or reply…",
            }),
        }
        labels = {"body": "Internal Note"}


class CloseTicketForm(forms.Form):
    """Closing tickets requires a reason for audit trail purposes."""

    REASONS = [
        ("Resolved", "Resolved"),
        ("Duplicate ticket", "Duplicate ticket"),
        ("Request cancelled", "Request cancelled"),
        ("Resolved by user", "Resolved by user"),
        ("Other", "Other"),
    ]

    RELOCATION_ACTIONS = [
        ("Relokasi", "Relocation"),
        ("Dismantle", "Dismantle"),
    ]

    # Standard tickets (Problem / Feature)
    reason_category = forms.ChoiceField(
        label="Resolution category", choices=REASONS, required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    # Relocation tickets (RC)
    relocation_action = forms.ChoiceField(
        label="Action", choices=RELOCATION_ACTIONS, required=False,
        widget=forms.Select(attrs={"class": "form-select", "id": "id_relocation_action"}),
    )
    new_site = forms.CharField(
        label="New site", required=False,
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "New site code / name…"}),
    )
    new_address = forms.CharField(
        label="New address", required=False,
        widget=forms.Textarea(attrs={
            "class": "form-textarea", "rows": 2,
            "placeholder": "New location address…",
        }),
    )

    # Closing notes
    reason = forms.CharField(
        label="Closing note", required=False, widget=forms.Textarea(attrs={
            "class": "form-textarea", "rows": 3,
            "placeholder": "Root cause or description of resolution taken…",
        }),
    )
