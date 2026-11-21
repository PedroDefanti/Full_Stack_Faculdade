from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from .models import Perfil


def org_atual(request):
    try:
        return request.user.perfil.organizacao
    except Perfil.DoesNotExist:
        raise PermissionDenied("Usuário sem organização.")


def papel_requerido(*papeis):  # NOVO
    """@papel_requerido("admin"): exige login e um desses papéis."""

    def decorador(view):
        @login_required
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            perfil = getattr(request.user, "perfil", None)
            if perfil is None or perfil.papel not in papeis:
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return wrapper

    return decorador