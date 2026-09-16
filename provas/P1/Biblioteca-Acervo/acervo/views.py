from datetime import date, timedelta
from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from .models import Autor, Emprestimo, Exemplar, Livro, Membro, Reserva
from django.contrib.auth.models import User


# --- CADASTRAR MEMBRO ---
def cadastrar_membro(request):
    if request.method == "POST":
        username = request.POST.get("username")
        telefone = request.POST.get("telefone")

        if username:
            # Cria o usuário base do Django ou reaproveita se existir
            user, created = User.objects.get_or_create(username=username)

            # Verifica se já é membro
            if hasattr(user, "membro"):
                messages.warning(
                    request, f"O usuário '{username}' já é um membro registrado."
                )
            else:
                Membro.objects.create(usuario=user, telefone=telefone or "")
                messages.success(
                    request, f"Membro '{username}' cadastrado com sucesso!"
                )
                return redirect("lista_livros")

    return render(request, "cadastrar_membro.html")


# --- PÁGINA INICIAL / LISTA DE LIVROS ---
def lista_livros(request):
    livros = Livro.objects.all()
    # Adicionamos contagem de exemplares disponíveis para exibição no template
    for livro in livros:
        livro.total_exemplares = livro.exemplares.count()
        livro.disponiveis = livro.exemplares.filter(
            status="disponivel"
        ).count()

    return render(request, "listar_livros.html", {"livros": livros})


# --- CADASTRAR AUTOR ---
def cadastrar_autor(request):
    if request.method == "POST":
        nome = request.POST.get("nome")
        if nome:
            Autor.objects.create(nome=nome)
            messages.success(request, f"Autor '{nome}' cadastrado com sucesso!")
            return redirect("cadastrar_livro")

    return render(request, "cadastrar_autor.html")


# --- CADASTRAR LIVRO (Com criação automática do 1º exemplar opcional) ---
def cadastrar_livro(request):
    if request.method == "POST":
        titulo = request.POST.get("titulo")
        autor_id = request.POST.get("autor_id")
        codigo_patrimonio = request.POST.get("codigo_patrimonio")

        if titulo and autor_id:
            autor = get_object_or_404(Autor, pk=autor_id)
            livro = Livro.objects.create(titulo=titulo, autor=autor)

            # Se o usuário informou um patrimônio/tombo inicial, cria o 1º exemplar
            if codigo_patrimonio:
                Exemplar.objects.create(
                    livro=livro,
                    codigo_patrimonio=codigo_patrimonio,
                    status="disponivel",
                )
                messages.success(
                    request,
                    f"Livro '{livro.titulo}' e exemplar '{codigo_patrimonio}' cadastrados!",
                )
            else:
                messages.warning(
                    request,
                    f"Livro '{livro.titulo}' cadastrado, mas sem exemplares. Cadastre ao menos um exemplar para permitir empréstimos.",
                )

            return redirect("lista_livros")

    autores = Autor.objects.all()
    return render(request, "cadastrar_livro.html", {"autores": autores})


# --- CADASTRAR EXEMPLAR ADICIONAL ---
def cadastrar_exemplar(request, livro_id=None):
    livro_selecionado = None
    if livro_id:
        livro_selecionado = get_object_or_404(Livro, pk=livro_id)

    if request.method == "POST":
        l_id = request.POST.get("livro_id")
        codigo = request.POST.get("codigo_patrimonio")

        if l_id and codigo:
            livro = get_object_or_404(Livro, pk=l_id)
            # Verifica se já existe um exemplar com este mesmo código
            if Exemplar.objects.filter(codigo_patrimonio=codigo).exists():
                messages.error(
                    request,
                    f"Já existe um exemplar com o código '{codigo}'. Use outro código.",
                )
            else:
                Exemplar.objects.create(
                    livro=livro, codigo_patrimonio=codigo, status="disponivel"
                )
                messages.success(
                    request,
                    f"Exemplar '{codigo}' adicionado ao livro '{livro.titulo}'!",
                )
                return redirect("lista_livros")

    livros = Livro.objects.all()
    return render(
        request,
        "cadastrar_exemplar.html",
        {"livros": livros, "livro_selecionado": livro_selecionado},
    )


# --- REALIZAR EMPRÉSTIMO OU ENTRAR NA FILA DE RESERVA ---
def solicitar_livro(request, livro_id):
    livro = get_object_or_404(Livro, pk=livro_id)

    if request.method == "POST":
        membro_id = request.POST.get("membro_id")
        membro = get_object_or_404(Membro, pk=membro_id)

        # 1. Verifica se existem exemplares cadastrados para o livro
        if not livro.exemplares.exists():
            messages.error(
                request,
                f"O livro '{livro.titulo}' ainda não tem exemplares físicos cadastrados.",
            )
            return redirect("cadastrar_exemplar", livro_id=livro.id)

        # 2. Busca por um exemplar disponível
        exemplar_disponivel = Exemplar.objects.filter(
            livro=livro, status="disponivel"
        ).first()

        if exemplar_disponivel:
            # Empréstimo realizado (prazo de 14 dias)
            Emprestimo.objects.create(
                exemplar=exemplar_disponivel,
                membro=membro,
                data_prevista_devolucao=date.today() + timedelta(days=14),
            )
            exemplar_disponivel.status = "emprestado"
            exemplar_disponivel.save()
            messages.success(
                request,
                f"Empréstimo do exemplar '{exemplar_disponivel.codigo_patrimonio}' realizado para {membro}!",
            )
        else:
            # Não há exemplar livre no momento -> Entra na Fila de Reserva
            Reserva.objects.create(livro=livro, membro=membro)
            messages.info(
                request,
                f"Todos os exemplares estão emprestados. {membro} entrou na fila de reserva.",
            )

        return redirect("lista_livros")

    membros = Membro.objects.all()
    return render(
        request,
        "solicitar_livro.html",
        {"livro": livro, "membros": membros},
    )


# --- FILA DE RESERVAS ---
def fila_reservas(request, livro_id):
    livro = get_object_or_404(Livro, pk=livro_id)
    reservas = Reserva.objects.filter(livro=livro, atendida=False).order_by(
        "data_reserva"
    )
    return render(
        request,
        "fila_reserva.html",
        {"livro": livro, "reservas": reservas},
    )


# --- LISTA DE EMPRÉSTIMOS ---
def lista_emprestimos(request):
    emprestimos = Emprestimo.objects.all().order_by("-data_emprestimo")
    return render(
        request,
        "lista_emprestimos.html",
        {"emprestimos": emprestimos},
    )


# --- DEVOLUÇÃO E TRANSFERÊNCIA DE RESERVA ---
def devolver_livro(request, emprestimo_id):
    emprestimo = get_object_or_404(Emprestimo, pk=emprestimo_id)

    if emprestimo.data_devolucao:
        messages.warning(request, "Este empréstimo já foi encerrado.")
        return redirect("lista_emprestimos")

    with transaction.atomic():
        emprestimo.data_devolucao = date.today()
        emprestimo.save()

        exemplar = emprestimo.exemplar

        # Verifica se há reserva pendente para o livro
        proxima_reserva = (
            Reserva.objects.filter(livro=exemplar.livro, atendida=False)
            .order_by("data_reserva")
            .first()
        )

        if proxima_reserva:
            # Atende a reserva e gera novo empréstimo imediatamente
            proxima_reserva.atendida = True
            proxima_reserva.save()

            Emprestimo.objects.create(
                exemplar=exemplar,
                membro=proxima_reserva.membro,
                data_prevista_devolucao=date.today() + timedelta(days=14),
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