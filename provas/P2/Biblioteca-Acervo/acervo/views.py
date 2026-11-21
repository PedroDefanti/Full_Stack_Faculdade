from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from core.utils import org_atual

from .forms import LivroForm
from .models import Autor, Emprestimo, Exemplar, Livro, Membro, Reserva


@login_required
def cadastrar_membro(request):
    org = org_atual(request)

    if request.method == "POST":
        username = request.POST.get("username")
        telefone = request.POST.get("telefone")

        if username:
            if User.objects.filter(username=username).exists():
                messages.error(
                    request,
                    f"O nome de usuário '{username}' já está em uso. Escolha outro.",
                )
            else:
                with transaction.atomic():
                    user = User(username=username)
                    user.set_unusable_password()
                    user.save()
                    Membro.objects.create(
                        usuario=user, telefone=telefone or "", organizacao=org
                    )
                messages.success(
                    request, f"Membro '{username}' cadastrado com sucesso!"
                )
                return redirect("lista_livros")

    return render(request, "cadastrar_membro.html")


@login_required
def lista_livros(request):
    org = org_atual(request)
    livros = (
        Livro.objects.filter(organizacao=org)
        .select_related("autor")
        .prefetch_related("exemplares")
    )

    for livro in livros:
        exemplares = livro.exemplares.all()  # vem do prefetch, sem consulta
        livro.total_exemplares = len(exemplares)
        livro.disponiveis = sum(1 for e in exemplares if e.status == "disponivel")

    return render(request, "listar_livros.html", {"livros": livros})


@login_required
def cadastrar_autor(request):
    org = org_atual(request)

    if request.method == "POST":
        nome = request.POST.get("nome")
        if nome:
            Autor.objects.create(nome=nome, organizacao=org)
            messages.success(request, f"Autor '{nome}' cadastrado com sucesso!")
            return redirect("cadastrar_livro")

    return render(request, "cadastrar_autor.html")


@login_required
def cadastrar_livro(request):
    org = org_atual(request)

    if request.method == "POST":
        form = LivroForm(request.POST, org=org)
        codigo_patrimonio = request.POST.get("codigo_patrimonio")

        if form.is_valid():
            if codigo_patrimonio and Exemplar.objects.filter(
                organizacao=org, codigo_patrimonio=codigo_patrimonio
            ).exists():
                form.add_error(None, "Já existe um exemplar com esse código.")
                messages.error(
                    request,
                    f"Já existe um exemplar com o código '{codigo_patrimonio}'.",
                )
            else:
                with transaction.atomic():
                    livro = form.save(commit=False)
                    livro.organizacao = org
                    livro.save()
                    form.save_m2m()

                    if codigo_patrimonio:
                        Exemplar.objects.create(
                            livro=livro,
                            codigo_patrimonio=codigo_patrimonio,
                            status="disponivel",
                            organizacao=org,
                        )

                if codigo_patrimonio:
                    messages.success(
                        request,
                        f"Livro '{livro.titulo}' e exemplar '{codigo_patrimonio}' cadastrados!",
                    )
                else:
                    messages.warning(
                        request,
                        f"Livro '{livro.titulo}' cadastrado, mas sem exemplares.",
                    )
                return redirect("lista_livros")
    else:
        form = LivroForm(org=org)

    autores = Autor.objects.filter(organizacao=org)
    return render(
        request, "cadastrar_livro.html", {"form": form, "autores": autores}
    )


@login_required
def cadastrar_exemplar(request, livro_id=None):
    org = org_atual(request)

    livro_selecionado = None
    if livro_id:
        livro_selecionado = get_object_or_404(Livro, pk=livro_id, organizacao=org)

    if request.method == "POST":
        l_id = request.POST.get("livro_id")
        codigo = request.POST.get("codigo_patrimonio")

        if l_id and codigo:
            livro = get_object_or_404(Livro, pk=l_id, organizacao=org)

            if Exemplar.objects.filter(
                organizacao=org, codigo_patrimonio=codigo
            ).exists():
                messages.error(
                    request,
                    f"Já existe um exemplar com o código '{codigo}'. Use outro código.",
                )
            else:
                Exemplar.objects.create(
                    livro=livro,
                    codigo_patrimonio=codigo,
                    status="disponivel",
                    organizacao=org,
                )
                messages.success(
                    request,
                    f"Exemplar '{codigo}' adicionado ao livro '{livro.titulo}'!",
                )
                return redirect("lista_livros")

    livros = Livro.objects.filter(organizacao=org).select_related("autor")
    return render(
        request,
        "cadastrar_exemplar.html",
        {"livros": livros, "livro_selecionado": livro_selecionado},
    )


@login_required
def solicitar_livro(request, livro_id):
    org = org_atual(request)
    livro = get_object_or_404(Livro, pk=livro_id, organizacao=org)

    if request.method == "POST":
        membro_id = request.POST.get("membro_id")
        membro = get_object_or_404(Membro, pk=membro_id, organizacao=org)

        if not livro.exemplares.exists():
            messages.error(
                request,
                f"O livro '{livro.titulo}' ainda não tem exemplares físicos cadastrados.",
            )
            return redirect("cadastrar_exemplar", livro_id=livro.id)

        exemplar_disponivel = Exemplar.objects.filter(
            organizacao=org, livro=livro, status="disponivel"
        ).first()

        if exemplar_disponivel:
            Emprestimo.objects.create(
                exemplar=exemplar_disponivel,
                membro=membro,
                data_prevista_devolucao=date.today() + timedelta(days=14),
                organizacao=org,
            )
            exemplar_disponivel.status = "emprestado"
            exemplar_disponivel.save()
            messages.success(
                request,
                f"Empréstimo do exemplar '{exemplar_disponivel.codigo_patrimonio}' realizado para {membro}!",
            )
        else:
            Reserva.objects.create(livro=livro, membro=membro, organizacao=org)
            messages.info(
                request,
                f"Todos os exemplares estão emprestados. {membro} entrou na fila de reserva.",
            )

        return redirect("lista_livros")

    membros = Membro.objects.filter(organizacao=org).select_related("usuario")
    return render(
        request,
        "solicitar_livro.html",
        {"livro": livro, "membros": membros},
    )


@login_required
def fila_reservas(request, livro_id):
    org = org_atual(request)
    livro = get_object_or_404(Livro, pk=livro_id, organizacao=org)
    reservas = (
        Reserva.objects.filter(organizacao=org, livro=livro, atendida=False)
        .select_related("membro__usuario")
        .order_by("data_reserva")
    )
    return render(
        request,
        "fila_reserva.html",
        {"livro": livro, "reservas": reservas},
    )


@login_required
def lista_emprestimos(request):
    org = org_atual(request)
    emprestimos = (
        Emprestimo.objects.filter(organizacao=org)
        .select_related("exemplar__livro", "membro__usuario")
        .order_by("-data_emprestimo")
    )
    return render(
        request,
        "lista_emprestimos.html",
        {"emprestimos": emprestimos},
    )


@login_required
def devolver_livro(request, emprestimo_id):
    org = org_atual(request)
    emprestimo = get_object_or_404(Emprestimo, pk=emprestimo_id, organizacao=org)

    if emprestimo.data_devolucao:
        messages.warning(request, "Este empréstimo já foi encerrado.")
        return redirect("lista_emprestimos")

    with transaction.atomic():
        emprestimo.data_devolucao = date.today()
        emprestimo.save()

        exemplar = emprestimo.exemplar

        proxima_reserva = (
            Reserva.objects.filter(
                organizacao=org, livro=exemplar.livro, atendida=False
            )
            .order_by("data_reserva")
            .first()
        )

        if proxima_reserva:
            proxima_reserva.atendida = True
            proxima_reserva.save()

            Emprestimo.objects.create(
                exemplar=exemplar,
                membro=proxima_reserva.membro,
                data_prevista_devolucao=date.today() + timedelta(days=14),
                organizacao=org,
            )
            messages.success(
                request,
                f"Livro devolvido! Como havia uma reserva, o exemplar foi atribuído a {proxima_reserva.membro}.",
            )
        else:
            exemplar.status = "disponivel"
            exemplar.save()
            messages.success(
                request,
                f"Devolução realizada! Multa: R$ {emprestimo.valor_multa:.2f}",
            )

    return redirect("lista_emprestimos")


@login_required
def buscar_livro(request):
    org = org_atual(request)
    busca = request.GET.get("pesquisa", default="")
    status = request.GET.get("status", default="todos")

    filtro_total = Q()
    if busca:
        filtro_total &= Q(titulo__icontains=busca) | Q(autor__nome__icontains=busca)

    resultados = (
        Livro.objects.filter(organizacao=org)
        .filter(filtro_total)
        .select_related("autor")
        .prefetch_related("exemplares")  # as properties tem_* usam isto
    )

    if status == "disponivel":
        resultados = resultados.filter(exemplares__status="disponivel")
    elif status == "emprestado":
        resultados = resultados.filter(exemplares__status="emprestado")
    elif status == "manutencao":
        resultados = resultados.filter(exemplares__status="manutencao")

    resultados = resultados.distinct()

    return render(
        request,
        "buscar_livro.html",
        {"resultados": resultados, "status_atual": status},
    )