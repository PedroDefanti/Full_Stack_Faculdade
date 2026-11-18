from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST


def login_view(request):
    if request.user.is_authenticated:
        return redirect("lista_livros")

    form = AuthenticationForm(request, data=request.POST or None)
    proximo = request.POST.get("next") or request.GET.get("next", "")

    if request.method == "POST" and form.is_valid():
        user = form.get_user()

        if not hasattr(user, "perfil"):
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
            return redirect("lista_livros")

    return render(
        request, "login.html", {"form": form, "next": proximo}
    )


@require_POST
def logout_view(request):
    logout(request)
    return redirect("login")
