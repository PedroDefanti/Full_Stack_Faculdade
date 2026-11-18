from django.core.exceptions import PermissionDenied

from .models import Perfil


def org_atual(request):
    try:
        return request.user.perfil.organizacao
    except Perfil.DoesNotExist:
        # superusuário/usuário sem Perfil: bloqueia (decisão a revisitar na Aula 15)
        raise PermissionDenied("Usuário sem organização.")