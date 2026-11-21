from datetime import date, timedelta
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, F, Max, Q
from django.db.models.functions import TruncDate, TruncMonth
from django.shortcuts import redirect, render
from django.utils import timezone

from core.models import Organizacao, Perfil, RegistroLogin
from core.utils import org_atual

from .models import Emprestimo, Exemplar, Livro, Membro, Reserva

PERIODOS = [(7, "7 dias"), (30, "30 dias"), (90, "90 dias"), (365, "1 ano")]
STATUS_NOMES = [
    ("disponivel", "Disponíveis"),
    ("emprestado", "Emprestados"),
    ("manutencao", "Em manutenção"),
]


# ---------- utilitários ----------

def superuser_required(view):
    """Só superusuário. Usado no painel admin, que é global de propósito."""

    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper


def _periodo(request):
    """Lê ?dias=... e devolve (dias, data_inicial, datetime_inicial)."""
    try:
        dias = int(request.GET.get("dias", 30))
    except ValueError:
        dias = 30
    if dias not in {d for d, _ in PERIODOS}:
        dias = 30
    return (
        dias,
        date.today() - timedelta(days=dias),
        timezone.now() - timedelta(days=dias),
    )


def _ultimos_meses(n=6):
    primeiro_do_mes = date.today().replace(day=1)
    meses = []
    for i in range(n - 1, -1, -1):
        ano, mes = primeiro_do_mes.year, primeiro_do_mes.month - i
        while mes <= 0:
            mes += 12
            ano -= 1
        meses.append(date(ano, mes, 1))
    return meses


def _serie_mensal(qs, campo, n=6):
    """Contagem por mês nos últimos n meses (qs já deve vir filtrado por data)."""
    meses = _ultimos_meses(n)
    contagem = {}
    linhas = (
        qs.annotate(m=TruncMonth(campo))
        .values_list("m")
        .annotate(total=Count("id"))
        .order_by("m")
    )
    for mes, total in linhas:
        contagem[(mes.year, mes.month)] = total
    return {
        "labels": [f"{m.month:02d}/{m.year}" for m in meses],
        "valores": [contagem.get((m.year, m.month), 0) for m in meses],
    }


def _logins_por_dia(qs, n):
    hoje = timezone.localdate()
    dias = [hoje - timedelta(days=i) for i in range(n - 1, -1, -1)]
    contagem = dict(
        qs.filter(criado_em__date__gte=dias[0])
        .annotate(dia=TruncDate("criado_em"))
        .values_list("dia")
        .annotate(total=Count("id"))
        .order_by("dia")
    )
    return {
        "labels": [d.strftime("%d/%m") for d in dias],
        "valores": [contagem.get(d, 0) for d in dias],
    }


def _status_exemplares(exemplares):
    contagem = dict(
        exemplares.values_list("status").annotate(n=Count("id")).order_by()
    )
    grafico = {
        "labels": [nome for _, nome in STATUS_NOMES],
        "valores": [contagem.get(codigo, 0) for codigo, _ in STATUS_NOMES],
    }
    return grafico, contagem


def _moeda(valor):
    return f"R$ {valor:.2f}".replace(".", ",")


# ---------- dashboard do cliente (uma organização) ----------

@login_required
def dashboard_org(request):
    # superusuário sem Perfil não tem organização: vai para o painel admin
    if request.user.is_superuser and not hasattr(request.user, "perfil"):
        return redirect("dashboard_admin")

    org = org_atual(request)
    dias, desde, desde_dt = _periodo(request)
    hoje = date.today()

    livros = Livro.objects.filter(organizacao=org)
    exemplares = Exemplar.objects.filter(organizacao=org)
    emprestimos = Emprestimo.objects.filter(organizacao=org)
    emprestimos_periodo = emprestimos.filter(data_emprestimo__gte=desde)
    ativos = emprestimos.filter(data_devolucao__isnull=True)
    atrasados = ativos.filter(data_prevista_devolucao__lt=hoje)
    logins = RegistroLogin.objects.filter(organizacao=org)
    logins_periodo = logins.filter(criado_em__gte=desde_dt)

    grafico_status, por_status = _status_exemplares(exemplares)
    total_exemplares = exemplares.count()
    emprestados = por_status.get("emprestado", 0)
    ocupacao = round(100 * emprestados / total_exemplares) if total_exemplares else 0

    # multas: empréstimos devolvidos com atraso + abertos já vencidos
    com_multa = emprestimos.filter(
        Q(data_devolucao__isnull=True, data_prevista_devolucao__lt=hoje)
        | Q(data_devolucao__gt=F("data_prevista_devolucao"))
    )
    multas_total = sum(e.valor_multa for e in com_multa)

    top_livros = list(
        emprestimos_periodo.values_list("exemplar__livro__titulo")
        .annotate(total=Count("id"))
        .order_by("-total", "exemplar__livro__titulo")[:5]
    )
    top_autores = list(
        emprestimos_periodo.values_list("exemplar__livro__autor__nome")
        .annotate(total=Count("id"))
        .order_by("-total", "exemplar__livro__autor__nome")[:5]
    )
    top_membros = list(
        emprestimos_periodo.values_list("membro__usuario__username")
        .annotate(total=Count("id"))
        .order_by("-total", "membro__usuario__username")[:5]
    )
    fila = list(
        Reserva.objects.filter(organizacao=org, atendida=False)
        .values_list("livro__titulo")
        .annotate(total=Count("id"))
        .order_by("-total", "livro__titulo")[:5]
    )
    top_usuarios = list(
        logins_periodo.values_list("usuario__username")
        .annotate(total=Count("id"))
        .order_by("-total", "usuario__username")[:5]
    )

    atrasados_total = atrasados.count()
    lista_atrasados = atrasados.select_related(
        "exemplar__livro", "membro__usuario"
    ).order_by("data_prevista_devolucao")[:8]

    livros_parados = (
        livros.exclude(exemplares__emprestimo__data_emprestimo__gte=desde)
        .select_related("autor")
        .order_by("titulo")[:5]
    )

    graficos = {
        "status": grafico_status,
        "meses": _serie_mensal(
            emprestimos.filter(
                data_emprestimo__gte=_ultimos_meses(6)[0]
            ),
            "data_emprestimo",
        ),
        "logins": _logins_por_dia(logins, min(dias, 30)),
        "top_livros": {
            "labels": [t for t, _ in top_livros],
            "valores": [n for _, n in top_livros],
        },
    }

    return render(
        request,
        "dashboard/org.html",
        {
            "org": org,
            "dias": dias,
            "periodos": PERIODOS,
            "total_titulos": livros.count(),
            "total_exemplares": total_exemplares,
            "ocupacao": f"{ocupacao}%",
            "total_membros": Membro.objects.filter(organizacao=org).count(),
            "emprestimos_periodo": emprestimos_periodo.count(),
            "emprestimos_ativos": ativos.count(),
            "atrasados_total": atrasados_total,
            "cor_atrasados": "text-danger" if atrasados_total else "text-success",
            "multas": _moeda(multas_total),
            "reservas_fila": Reserva.objects.filter(
                organizacao=org, atendida=False
            ).count(),
            "logins_periodo": logins_periodo.count(),
            "usuarios_logaram": logins_periodo.values("usuario").distinct().count(),
            "logins_hoje": logins.filter(criado_em__date=timezone.localdate()).count(),
            "top_livros": top_livros,
            "top_autores": top_autores,
            "top_membros": top_membros,
            "fila": fila,
            "top_usuarios": top_usuarios,
            "lista_atrasados": lista_atrasados,
            "livros_parados": livros_parados,
            "graficos": graficos,
        },
    )


# ---------- dashboard do admin (todas as organizações) ----------

@superuser_required
def dashboard_admin(request):
    dias, desde, desde_dt = _periodo(request)
    agora = timezone.now()
    hoje = date.today()

    def por_org(qs):
        return dict(
            qs.values_list("organizacao_id").annotate(n=Count("id")).order_by()
        )

    orgs = list(Organizacao.objects.order_by("nome"))
    usuarios = por_org(Perfil.objects.all())
    livros = por_org(Livro.objects.all())
    exemplares = por_org(Exemplar.objects.all())
    membros = por_org(Membro.objects.all())
    emp_periodo = por_org(Emprestimo.objects.filter(data_emprestimo__gte=desde))
    logins_periodo_qs = RegistroLogin.objects.filter(criado_em__gte=desde_dt)
    logins_org = por_org(logins_periodo_qs)
    ultimo_login = dict(
        RegistroLogin.objects.values_list("organizacao_id")
        .annotate(ultimo=Max("criado_em"))
        .order_by()
    )

    limite = agora - timedelta(days=30)
    linhas = []
    for o in orgs:
        ultimo = ultimo_login.get(o.id)
        linhas.append(
            {
                "org": o,
                "usuarios": usuarios.get(o.id, 0),
                "livros": livros.get(o.id, 0),
                "exemplares": exemplares.get(o.id, 0),
                "membros": membros.get(o.id, 0),
                "emprestimos": emp_periodo.get(o.id, 0),
                "logins": logins_org.get(o.id, 0),
                "ultimo_login": ultimo,
                "inativa": ultimo is None or ultimo < limite,
            }
        )
    linhas.sort(key=lambda l: (-l["emprestimos"], l["org"].nome))

    grafico_status, _ = _status_exemplares(Exemplar.objects.all())
    top_logins_org = sorted(linhas, key=lambda l: -l["logins"])[:8]

    top_livros = [
        (f"{titulo} · {org}", total)
        for titulo, org, total in Emprestimo.objects.filter(
            data_emprestimo__gte=desde
        )
        .values_list("exemplar__livro__titulo", "organizacao__nome")
        .annotate(total=Count("id"))
        .order_by("-total", "exemplar__livro__titulo")[:8]
    ]

    graficos = {
        "status": grafico_status,
        "logins": _logins_por_dia(RegistroLogin.objects.all(), min(dias, 30)),
        "meses": _serie_mensal(
            Emprestimo.objects.filter(data_emprestimo__gte=_ultimos_meses(6)[0]),
            "data_emprestimo",
        ),
        "novas_orgs": _serie_mensal(
            Organizacao.objects.filter(
                criada_em__date__gte=_ultimos_meses(6)[0]
            ),
            "criada_em",
        ),
        "logins_orgs": {
            "labels": [l["org"].nome for l in top_logins_org],
            "valores": [l["logins"] for l in top_logins_org],
        },
    }

    return render(
        request,
        "dashboard/admin.html",
        {
            "dias": dias,
            "periodos": PERIODOS,
            "total_orgs": len(orgs),
            "orgs_inativas": sum(1 for l in linhas if l["inativa"]),
            "total_usuarios": sum(usuarios.values()),
            "total_titulos": sum(livros.values()),
            "total_exemplares": sum(exemplares.values()),
            "total_membros": sum(membros.values()),
            "emprestimos_periodo": sum(emp_periodo.values()),
            "emprestimos_ativos": Emprestimo.objects.filter(
                data_devolucao__isnull=True
            ).count(),
            "atrasados_total": Emprestimo.objects.filter(
                data_devolucao__isnull=True, data_prevista_devolucao__lt=hoje
            ).count(),
            "logins_periodo": logins_periodo_qs.count(),
            "logins_hoje": RegistroLogin.objects.filter(
                criado_em__date=timezone.localdate()
            ).count(),
            "usuarios_logaram": logins_periodo_qs.values("usuario").distinct().count(),
            "linhas": linhas,
            "top_livros": top_livros,
            "ultimos_logins": RegistroLogin.objects.select_related(
                "usuario", "organizacao"
            ).order_by("-criado_em")[:10],
            "graficos": graficos,
        },
    )