from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordResetForm,
    SetPasswordForm,
)
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.template import loader

from leaderlodge.accounts.registration import unique_username_for_email

User = get_user_model()
logger = __import__("logging").getLogger(__name__)


def _form_control(widget):
    attrs = dict(widget.attrs)
    attrs.setdefault("class", "form-control")
    widget.attrs = attrs
    return widget


class EmailOrUsernameAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        label="Email or username",
        widget=forms.TextInput(
            attrs={
                "autofocus": True,
                "class": "form-control",
                "autocomplete": "username",
            }
        ),
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "autocomplete": "current-password",
            }
        ),
    )

    def clean_username(self):
        username = self.cleaned_data.get("username", "").strip()
        if "@" in username:
            matched = User.objects.filter(email__iexact=username).first()
            if matched is not None:
                return matched.get_username()
        return username


class SignupForm(forms.Form):
    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "autocomplete": "email",
            }
        ),
    )
    first_name = forms.CharField(
        label="First name",
        required=False,
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "autocomplete": "given-name",
            }
        ),
    )
    password1 = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "autocomplete": "new-password",
            }
        ),
    )
    password2 = forms.CharField(
        label="Confirm password",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "autocomplete": "new-password",
            }
        ),
    )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account with this email already exists.")
        return email

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data["password2"]
        if password1 and password2 and password1 != password2:
            raise ValidationError("The two password fields didn’t match.")
        return password2

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get("password1")
        if password1:
            password_validation.validate_password(password1)
        return cleaned

    def save(self):
        email = self.cleaned_data["email"]
        return User.objects.create_user(
            username=unique_username_for_email(email),
            email=email,
            password=self.cleaned_data["password1"],
            first_name=self.cleaned_data.get("first_name", "").strip(),
        )


class StyledPasswordResetForm(PasswordResetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _form_control(self.fields["email"].widget)

    def save(self, *args, **kwargs):
        email = self.cleaned_data["email"]
        users = list(self.get_users(email))
        if not users:
            logger.warning(
                "Password reset requested for email with no active matching account: %s",
                email,
            )
        else:
            logger.info(
                "Sending password reset email to %s for user pk(s) %s",
                email,
                [user.pk for user in users],
            )
        return super().save(*args, **kwargs)

    def send_mail(
        self,
        subject_template_name,
        email_template_name,
        context,
        from_email,
        to_email,
        html_email_template_name=None,
    ):
        subject = loader.render_to_string(subject_template_name, context)
        subject = "".join(subject.splitlines())
        body = loader.render_to_string(email_template_name, context)
        email_message = EmailMultiAlternatives(subject, body, from_email, [to_email])
        if html_email_template_name is not None:
            html_email = loader.render_to_string(html_email_template_name, context)
            email_message.attach_alternative(html_email, "text/html")
        try:
            email_message.send()
        except Exception:
            logger.exception(
                "Password reset email delivery failed for user pk %s",
                context["user"].pk,
            )
            raise


class StyledSetPasswordForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            _form_control(field.widget)
