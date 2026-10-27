from django import forms
from django.utils import timezone

from apps.accounts.models import User

from .models import Ticket, TicketReply, Company, CompanyService

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
        fields = ["name", "customer_id", "code", "partner", "contact_person", "contact_phone", "address", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. PT Telekomunikasi Indonesia"}),
            "customer_id": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. 050526015"}),
            "code": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. TELKOM"}),
            "partner": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. PLN Icon Plus (opsional)"}),
            "contact_person": forms.TextInput(attrs={"class": "form-input", "placeholder": "PIC Name"}),
            "contact_phone": forms.TextInput(attrs={"class": "form-input", "placeholder": "08xxxxxxxxxx"}),
            "address": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Office address..."}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check"}),
        }


class CompanyServiceForm(forms.ModelForm):
    """Form to add or edit services under a company."""

    class Meta:
        model = CompanyService
        fields = ["service_id", "service_name", "device_solution", "brand", "is_active"]
        widgets = {
            "service_id": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. 135600010"}),
            "service_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Managed Service Firewall"}),
            "device_solution": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Router (Mikrotik), Server"}),
            "brand": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Mikrotik, Versa, Acronis"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check"}),
        }


class TicketForm(forms.ModelForm):
    """Form to create and edit tickets."""

    company = forms.ChoiceField(
        label="Company / Unit",
        choices=[],
        widget=forms.Select(attrs={"class": "form-select", "id": "id_company"}),
        required=True,
    )

    class Meta:
        model = Ticket
        fields = [
            "ticket_type", "subject", "description", "address", "problem_category", "problem_detail",
            "priority", "status", "source", "company", "customer_id", "partner", "company_service",
            "service_id", "service_name", "device_solution", "brand", "tags", "requester_phone"
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
            "customer_id": forms.TextInput(attrs={"placeholder": "Customer ID (auto)", "id": "id_customer_id"}),
            "partner": forms.TextInput(attrs={"placeholder": "Partner (optional)", "id": "id_partner"}),
            "company_service": forms.Select(attrs={"class": "form-select", "id": "id_company_service"}),
            "service_id": forms.TextInput(attrs={"placeholder": "Service ID (auto)", "id": "id_service_id"}),
            "service_name": forms.TextInput(attrs={"placeholder": "Service / Product", "id": "id_service_name"}),
            "device_solution": forms.TextInput(attrs={"placeholder": "Device / Solution (auto)", "id": "id_device_solution"}),
            "brand": forms.TextInput(attrs={"placeholder": "Brand (auto)", "id": "id_brand"}),
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

        # Service catalog & Company fields
        self.fields["company_service"].required = False
        self.fields["company_service"].empty_label = "Select service / product (optional)..."
        self.fields["customer_id"].required = False
        self.fields["partner"].required = False
        self.fields["service_id"].required = False
        self.fields["service_name"].required = False
        self.fields["device_solution"].required = False
        self.fields["brand"].required = False

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

        # Auto-fill snapshot fields from company_service if chosen
        company_service = data.get("company_service")
        if company_service:
            if not data.get("service_id"):
                data["service_id"] = company_service.service_id
            if not data.get("service_name"):
                data["service_name"] = company_service.service_name
            if not data.get("device_solution"):
                data["device_solution"] = company_service.device_solution
            if not data.get("brand"):
                data["brand"] = company_service.brand
            if not data.get("customer_id") and getattr(company_service.company, "customer_id", None):
                data["customer_id"] = company_service.company.customer_id
            if not data.get("partner") and getattr(company_service.company, "partner", None):
                data["partner"] = company_service.company.partner
        else:
            # Fallback to Company's customer_id and partner if not specified
            company_name = data.get("company")
            if company_name:
                try:
                    c_obj = Company.objects.filter(name=company_name).first()
                    if c_obj:
                        if not data.get("customer_id") and c_obj.customer_id:
                            data["customer_id"] = c_obj.customer_id
                        if not data.get("partner") and c_obj.partner:
                            data["partner"] = c_obj.partner
                except Exception:
                    pass
            
        ticket_type = data.get("ticket_type")
        problem_category = data.get("problem_category")
        problem_detail = data.get("problem_detail")
        address = data.get("address")
        priority = data.get("priority")

        if ticket_type == Ticket.Type.PROBLEM:
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

    # Problem tickets (PR): update problem category upon closing
    problem_category = forms.ChoiceField(
        label="Problem Category",
        choices=[("", "Keep current / Not specified")] + list(Ticket.ProblemCategory.choices),
        required=False,
        widget=forms.Select(attrs={"class": "form-select", "id": "id_close_problem_category"}),
    )
    problem_detail = forms.CharField(
        label="Category Detail",
        required=False,
        widget=forms.TextInput(attrs={"class": "form-input", "id": "id_close_problem_detail", "placeholder": "Detail if Other..."}),
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
