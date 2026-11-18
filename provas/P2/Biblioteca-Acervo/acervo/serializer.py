from rest_framework import serializers

from core.utils import org_atual

from .models import Autor, Livro


class AutorDaOrganizacaoField(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        return Autor.objects.filter(organizacao=org_atual(self.context["request"]))


class LivroSerializer(serializers.ModelSerializer):
    autor = AutorDaOrganizacaoField()

    class Meta:
        model = Livro
        fields = ["id", "titulo", "autor", "ano"]