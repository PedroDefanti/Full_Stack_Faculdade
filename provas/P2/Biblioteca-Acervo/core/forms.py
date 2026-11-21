from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User


class BootstrapMixin:
    """Aplica form-control/placeholder e marca is-invalid nos campos com erro."""

    def estilizar(self):
        for nome, campo in self.fields.items():
            campo.widget.attrs.setdefault("class", "form-control")
            campo.widget.attrs.setdefault("placeholder", campo.label or nome)

    def full_clean(self):
        super().full_clean()
        for nome in self.errors:
            if nome in self.fields:
                self.fields[nome].widget.attrs["class"] = "form-control is-invalid"


class LoginForm(BootstrapMixin, AuthenticationForm):  # NOVO
    error_messages = {
        "invalid_login": "Usuário ou senha incorretos.",
        "inactive": "Esta conta está inativa.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Usuário"
        self.fields["password"].label = "Senha"
        self.estilizar()


class RegistroForm(BootstrapMixin, UserCreationForm):  # MUDOU
    organizacao = forms.CharField(
        max_length=120,
        label="Nome da organização",
        help_text="Ex.: Biblioteca Municipal de Maricá",
    )

    field_order = ["organizacao", "username", "password1", "password2"]

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Usuário"
        self.fields["username"].help_text = "Letras, números e @/./+/-/_."
        self.fields["password1"].label = "Senha"
        self.fields["password2"].label = "Confirmar senha"
        self.fields["password2"].help_text = ""
        self.estilizar()