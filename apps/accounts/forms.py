from django import forms
from django.contrib.auth.forms import AuthenticationForm

from .models import User


class LoginForm(AuthenticationForm):
    """Form login dengan atribut yang dibutuhkan tampilan."""

    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "Username atau password salah. Periksa kembali.",
        "inactive": "Akun ini tidak aktif. Hubungi administrator.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update({
            "class": "form-input",
            "placeholder": "Masukkan username",
            "autofocus": True,
            "autocomplete": "username",
        })
        self.fields["password"].widget.attrs.update({
            "class": "form-input",
            "placeholder": "Masukkan password",
            "autocomplete": "current-password",
        })
        self.fields["username"].label = "Username"
        self.fields["password"].label = "Password"


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "phone", "nik",
                  "department", "position", "shift"]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-input"}),
            "last_name": forms.TextInput(attrs={"class": "form-input"}),
            "email": forms.EmailInput(attrs={"class": "form-input"}),
            "phone": forms.TextInput(attrs={"class": "form-input",
                                            "placeholder": "08xx-xxxx-xxxx"}),
            "nik": forms.TextInput(attrs={"class": "form-input"}),
            "department": forms.TextInput(attrs={"class": "form-input"}),
            "position": forms.TextInput(attrs={"class": "form-input"}),
            "shift": forms.Select(attrs={"class": "form-select"}),
        }
