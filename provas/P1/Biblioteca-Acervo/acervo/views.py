from datetime import date, timedelta
from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from .models import Autor, Emprestimo, Exemplar, Livro, Membro, Reserva
from django.contrib.auth.models import User
from django.db.models import Q
from .forms import LivroForm



def cadastrar_membro(request):
    if request.method == "POST":
        username = request.POST.get("username")
        telefone = request.POST.get("telefone")

        if username:
            
            user, created = User.objects.get_or_create(username=username)

           
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



def lista_livros(request):
    livros = Livro.objects.all()
    
    for livro in livros:
        livro.total_exemplares = livro.exemplares.count()
        livro.disponiveis = livro.exemplares.filter(
            status="disponivel"
        ).count()

    return render(request, "listar_livros.html", {"livros": livros})



def cadastrar_autor(request):
    if request.method == "POST":
        nome = request.POST.get("nome")
        if nome:
            Autor.objects.create(nome=nome)
            messages.success(request, f"Autor '{nome}' cadastrado com sucesso!")
            return redirect("cadastrar_livro")

    return render(request, "cadastrar_autor.html")



def cadastrar_livro(request):
    if request.method == "POST":
        form = LivroForm(request.POST)
        codigo_patrimonio = request.POST.get("codigo_patrimonio")

        if form.is_valid():
            livro = form.save()

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
                    f"Livro '{livro.titulo}' cadastrado, mas sem exemplares.",
                )

            return redirect("lista_livros")
    else:
        form = LivroForm()

   
    autores = Autor.objects.all()

    return render(
        request, "cadastrar_livro.html", {"form": form, "autores": autores}
    )



def cadastrar_exemplar(request, livro_id=None):
    livro_selecionado = None
    if livro_id:
        livro_selecionado = get_object_or_404(Livro, pk=livro_id)

    if request.method == "POST":
        l_id = request.POST.get("livro_id")
        codigo = request.POST.get("codigo_patrimonio")

        if l_id and codigo:
            livro = get_object_or_404(Livro, pk=l_id)

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



def solicitar_livro(request, livro_id):
    livro = get_object_or_404(Livro, pk=livro_id)

    if request.method == "POST":
        membro_id = request.POST.get("membro_id")
        membro = get_object_or_404(Membro, pk=membro_id)


        if not livro.exemplares.exists():
            messages.error(
                request,
                f"O livro '{livro.titulo}' ainda não tem exemplares físicos cadastrados.",
            )
            return redirect("cadastrar_exemplar", livro_id=livro.id)


        exemplar_disponivel = Exemplar.objects.filter(
            livro=livro, status="disponivel"
        ).first()

        if exemplar_disponivel:

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



def lista_emprestimos(request):
    emprestimos = Emprestimo.objects.all().order_by("-data_emprestimo")
    return render(
        request,
        "lista_emprestimos.html",
        {"emprestimos": emprestimos},
    )



def devolver_livro(request, emprestimo_id):
    emprestimo = get_object_or_404(Emprestimo, pk=emprestimo_id)

    if emprestimo.data_devolucao:
        messages.warning(request, "Este empréstimo já foi encerrado.")
        return redirect("lista_emprestimos")

    with transaction.atomic():
        emprestimo.data_devolucao = date.today()
        emprestimo.save()

        exemplar = emprestimo.exemplar

        proxima_reserva = (
            Reserva.objects.filter(livro=exemplar.livro, atendida=False)
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


from django.db.models import Q
from django.shortcuts import render
from .models import Livro


def buscar_livro(request):
    busca = request.GET.get("pesquisa", default="")
    status = request.GET.get("status", default="todos")

    filtro_total = Q()

  
    if busca:
        filtro_total &= Q(titulo__icontains=busca) | Q(
            autor__nome__icontains=busca
        )

    resultados = Livro.objects.filter(filtro_total).select_related("autor")

    
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


