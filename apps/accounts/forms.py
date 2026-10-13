from django import forms
from django.contrib.auth.forms import AuthenticationForm

from .models import User


class LoginForm(AuthenticationForm):
    """Form login dengan atribut yang dibutuhkan tampilan."""

    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "Invalid username or password. Please check and try again.",
        "inactive": "This account is inactive. Please contact an administrator.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update({
            "class": "form-input",
            "placeholder": "Enter your username",
            "autofocus": True,
            "autocomplete": "username",
        })
        self.fields["password"].widget.attrs.update({
            "class": "form-input",
            "placeholder": "Enter your password",
            "autocomplete": "current-password",
        })
        self.fields["username"].label = "Username"
        self.fields["password"].label = "Password"


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "nik", "position"]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-input"}),
            "last_name": forms.TextInput(attrs={"class": "form-input"}),
            "email": forms.EmailInput(attrs={"class": "form-input"}),
            "nik": forms.TextInput(attrs={"class": "form-input"}),
            "position": forms.TextInput(attrs={"class": "form-input"}),
        }
