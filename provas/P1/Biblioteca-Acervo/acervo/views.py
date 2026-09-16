from datetime import date, timedelta
from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from .models import Emprestimo, Exemplar, Livro, Membro, Reserva,Autor


# --- PÁGINA INICIAL / LISTA DE LIVROS ---
def lista_livros(request):
    livros = Livro.objects.all()
    return render(request, "listar_livros.html", {"livros": livros})


# --- REALIZAR EMPRÉSTIMO OU ENTRAR NA FILA DE RESERVA ---
def solicitar_livro(request, livro_id):
    livro = get_object_or_404(Livro, pk=livro_id)

    if request.method == "POST":
        membro_id = request.POST.get("membro_id")
        membro = get_object_or_404(Membro, pk=membro_id)

        # Procura por um exemplar disponível
        exemplar_disponivel = Exemplar.objects.filter(
            livro=livro, status="disponivel"
        ).first()

        if exemplar_disponivel:
            # Se houver exemplar disponível, cria o empréstimo (devolução em 14 dias)
            Emprestimo.objects.create(
                exemplar=exemplar_disponivel,
                membro=membro,
                data_prevista_devolucao=date.today() + timedelta(days=14),
            )
            exemplar_disponivel.status = "emprestado"
            exemplar_disponivel.save()
            messages.success(
                request,
                f"Empréstimo do livro '{livro.titulo}' realizado com sucesso!",
            )
        else:
            # Se não houver exemplar disponível, insere na Fila de Reserva
            Reserva.objects.create(livro=livro, membro=membro)
            messages.info(
                request,
                f"Sem exemplares disponíveis. Você entrou na fila de reserva para '{livro.titulo}'.",
            )

        return redirect("lista_livros")

    membros = Membro.objects.all()
    return render(
        request,
        "solicitar_livro.html",
        {"livro": livro, "membros": membros},
    )


# --- MINHAS RESERVAS / FILA DE ESPERA ---
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


# --- LISTA DE EMPRÉSTIMOS E CÁLCULO DE MULTAS ---
def lista_emprestimos(request):
    emprestimos = Emprestimo.objects.all().order_by("-data_emprestimo")
    return render(
        request,
        "lista_emprestimos.html",
        {"emprestimos": emprestimos},
    )


# --- DEVOLUÇÃO DE EXEMPLAR ---
def devolver_livro(request, emprestimo_id):
    emprestimo = get_object_or_404(Emprestimo, pk=emprestimo_id)

    if emprestimo.data_devolucao:
        messages.warning(request, "Este livro já foi devolvido.")
        return redirect("lista_emprestimos")

    with transaction.atomic():
        emprestimo.data_devolucao = date.today()
        emprestimo.save()

        exemplar = emprestimo.exemplar

        # Verifica se há alguém na fila de reserva para este livro
        proxima_reserva = (
            Reserva.objects.filter(livro=exemplar.livro, atendida=False)
            .order_by("data_reserva")
            .first()
        )

        if proxima_reserva:
            # Atende a reserva automaticamente e gera novo empréstimo
            proxima_reserva.atendida = True
            proxima_reserva.save()

            Emprestimo.objects.create(
                exemplar=exemplar,
                membro=proxima_reserva.membro,
                data_prevista_devolucao=date.today() + timedelta(days=14),
            )
            messages.success(
                request,
                f"Livro devolvido! Havia uma reserva, e o exemplar foi transferido para {proxima_reserva.membro}.",
            )
        else:
            exemplar.status = "disponivel"
            exemplar.save()
            messages.success(
                request,
                f"Livro devolvido com sucesso! Multa calculada: R$ {emprestimo.valor_multa:.2f}",
            )

    return redirect("lista_emprestimos")

def cadastrar_autor(request):
    if request.method == "POST":
        nome = request.POST.get("nome")
        if nome:
            Autor.objects.create(nome=nome)
            messages.success(request, f"Autor '{nome}' cadastrado com sucesso!")
            return redirect("cadastrar_livro")

    return render(request, "cadastrar_autor.html")


# --- CADASTRAR LIVRO ---
def cadastrar_livro(request):
    if request.method == "POST":
        titulo = request.POST.get("titulo")
        autor_id = request.POST.get("autor_id")

        if titulo and autor_id:
            autor = get_object_or_404(Autor, pk=autor_id)
            livro = Livro.objects.create(titulo=titulo, autor=autor)
            messages.success(
                request,
                f"Livro '{livro.titulo}' cadastrado! Agora cadastre os exemplares.",
            )
            return redirect("cadastrar_exemplar", livro_id=livro.id)

    autores = Autor.objects.all()
    return render(request, "cadastrar_livro.html", {"autores": autores})


# --- CADASTRAR EXEMPLAR (CÓDIGO DE PATRIMÔNIO) ---
def cadastrar_exemplar(request, livro_id=None):
    livro_selecionado = None
    if livro_id:
        livro_selecionado = get_object_or_404(Livro, pk=livro_id)

    if request.method == "POST":
        l_id = request.POST.get("livro_id")
        codigo = request.POST.get("codigo_patrimonio")

        if l_id and codigo:
            livro = get_object_or_404(Livro, pk=l_id)
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
        "cadastrar_exemplar.html",)