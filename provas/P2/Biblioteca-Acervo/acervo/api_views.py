from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.utils import org_atual

from .dashboard import metricas_org
from .forms import PeriodoForm
from .models import Livro
from .serializers import LivroSerializer


class LivroDaOrganizacaoMixin:
    serializer_class = LivroSerializer

    def get_queryset(self):
        return Livro.objects.filter(organizacao=org_atual(self.request))


class LivroListCreate(LivroDaOrganizacaoMixin, generics.ListCreateAPIView):
    def perform_create(self, serializer):
        serializer.save(organizacao=org_atual(self.request))


class LivroDetail(LivroDaOrganizacaoMixin, generics.RetrieveUpdateDestroyAPIView):
    pass


class DashboardApi(APIView):  # NOVO
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org = org_atual(request)
        form = PeriodoForm(request.GET)
        if not form.is_valid():
            return Response(form.errors.get_json_data(), status=400)

        dados = metricas_org(org, form.cleaned_data["inicio"], form.cleaned_data["fim"])
        if not request.user.perfil.eh_admin:
            dados.pop("por_mes")  # operador não recebe séries
        return Response(dados)