from datetime import date
from django import forms
from .models import Autor, Livro


class LivroForm(forms.ModelForm):
    class Meta:
        model = Livro
        fields = ["titulo", "autor", "ano"]

    def __init__(self, *args, org=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["autor"].queryset = Autor.objects.filter(organizacao=org)

    def clean_ano(self):
        ano_livro = self.cleaned_data.get("ano")
        ano_atual = date.today().year

        if ano_livro and ano_livro > ano_atual:
            raise forms.ValidationError(
                f"O ano de publicação ({ano_livro}) não pode ser maior do que o ano atual"
            )
        return ano_livro


# ---------- Aula 17: período validado ----------

def _data():
    return forms.DateInput(
        format="%Y-%m-%d",
        attrs={"type": "date", "class": "form-control form-control-sm"},
    )


class PeriodoForm(forms.Form):
    inicio = forms.DateField(required=False, label="Início", widget=_data())
    fim = forms.DateField(required=False, label="Fim", widget=_data())

    def clean(self):
        dados = super().clean()
        inicio, fim = dados.get("inicio"), dados.get("fim")
        if inicio and fim and inicio > fim:
            raise forms.ValidationError(
                "A data inicial não pode ser maior que a data final."
            )
        return dados


def periodo_validado(params):
    """(form, inicio, fim). Data inválida vira None: a URL nunca gera erro 500."""
    form = PeriodoForm(params)
    inicio = fim = None
    if form.is_valid():
        inicio, fim = form.cleaned_data["inicio"], form.cleaned_data["fim"]
    return form, inicio, fim


def aplicar_periodo(qs, campo, inicio, fim):
    """campo: 'data_emprestimo' (DateField) ou 'criado_em__date' (DateTimeField)."""
    if inicio:
        qs = qs.filter(**{f"{campo}__gte": inicio})
    if fim:
        qs = qs.filter(**{f"{campo}__lte": fim})
    return qs


def filtrar_periodo(request, qs, campo="data_emprestimo"):
    """Versão do slide: lê o período direto do request."""
    _, inicio, fim = periodo_validado(request.GET)
    return aplicar_periodo(qs, campo, inicio, fim)