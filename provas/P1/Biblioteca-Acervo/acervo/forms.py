from datetime import date
from django import forms
from .models import Livro


class LivroForm(forms.ModelForm):

    class Meta:
        model = Livro
        fields = ["titulo", "autor", "ano"]

    def clean_ano(self):
        ano_livro = self.cleaned_data.get("ano")
        ano_atual = date.today().year

        if ano_livro and ano_livro > ano_atual:
            raise forms.ValidationError(
                f"O ano de publicação ({ano_livro}) não pode ser maior do que o ano atual"
            )

        return ano_livro
