from django.contrib import messages
from django.contrib.auth import login, logout
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import LoginForm, RegistroForm
from .models import Organizacao, Perfil


def _destino_inicial(user):
    """Superusuário sem Perfil vai para o painel admin; os demais, para o dashboard."""
    if user.is_superuser and not hasattr(user, "perfil"):
        return "dashboard_admin"
    return "dashboard"


def login_view(request):
    if request.user.is_authenticated:
        return redirect(_destino_inicial(request.user))

    form = LoginForm(request, data=request.POST or None)
    proximo = request.POST.get("next") or request.GET.get("next", "")

    if request.method == "POST" and form.is_valid():
        user = form.get_user()

        if not hasattr(user, "perfil") and not user.is_superuser:  # MUDOU
            messages.error(
                request,
                "Este usuário não está vinculado a nenhuma organização. "
                "Peça ao administrador para criar o Perfil.",
            )
        else:
            login(request, user)
            # só segue o "next" se for um endereço do próprio site
            if proximo and url_has_allowed_host_and_scheme(
                proximo,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(proximo)
            return redirect(_destino_inicial(user))  # MUDOU

    return render(
        request, "login.html", {"form": form, "next": proximo}
    )


def registro_view(request):
    if request.user.is_authenticated:
        return redirect(_destino_inicial(request.user))

    form = RegistroForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        # usuário, organização e perfil nascem juntos ou não nascem
        with transaction.atomic():
            user = form.save()
            org = Organizacao.objects.create(nome=form.cleaned_data["organizacao"])
            Perfil.objects.create(usuario=user, organizacao=org, papel="admin")  # MUDOU

        login(request, user)
        messages.success(
            request, f"Conta criada! Organização '{org.nome}' pronta para uso."
        )
        return redirect("dashboard")  # MUDOU

    return render(request, "registro.html", {"form": form})


@require_POST
def logout_view(request):
    logout(request)
    return redirect("login")