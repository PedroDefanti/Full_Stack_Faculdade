from rest_framework import generics

from core.utils import org_atual

from .models import Livro
from .serializer import LivroSerializer


class LivroDaOrganizacaoMixin:
    serializer_class = LivroSerializer

    def get_queryset(self):
        return Livro.objects.filter(organizacao=org_atual(self.request))


class LivroListCreate(LivroDaOrganizacaoMixin, generics.ListCreateAPIView):
    def perform_create(self, serializer):
        serializer.save(organizacao=org_atual(self.request))


class LivroDetail(
    LivroDaOrganizacaoMixin, generics.RetrieveUpdateDestroyAPIView
):
    pass