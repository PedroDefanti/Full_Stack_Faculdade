from datetime import date, timedelta
from functools import wraps
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, F, Max, Q
from django.db.models.functions import TruncDate, TruncMonth
from django.shortcuts import redirect, render
from django.utils import timezone

from core.models import Organizacao, Perfil, RegistroLogin
from core.utils import org_atual

from .forms import aplicar_periodo, periodo_validado
from .models import Emprestimo, Exemplar, Livro, Membro, Reserva

STATUS_NOMES = [
    ("disponivel", "Disponíveis"),
    ("emprestado", "Emprestados"),
    ("manutencao", "Em manutenção"),
]


# ---------- utilitários ----------

def superuser_required(view):
    """Só superusuário. O painel admin é global de propósito."""

    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper


def _moeda(valor):
    return f"R$ {valor:.2f}".replace(".", ",")


def _periodo_qs(inicio, fim):
    """Querystring do período, repassada aos links de exportação."""
    params = {}
    if inicio:
        params["inicio"] = inicio.isoformat()
    if fim:
        params["fim"] = fim.isoformat()
    return urlencode(params)


def _ranking(qs, campo, n=5):
    linhas = (
        qs.values_list(campo)
        .annotate(total=Count("id"))
        .order_by("-total", campo)[:n]
    )
    return [{"nome": nome, "total": total} for nome, total in linhas]


def _meses_contiguos(pares):
    """[(data, total)] -> [{'mes': '08/2026', 'total': 22}] sem buracos."""
    if not pares:
        return []
    contagem = {(m.year, m.month): t for m, t in pares}
    ano, mes = pares[0][0].year, pares[0][0].month
    ult_ano, ult_mes = pares[-1][0].year, pares[-1][0].month
    saida = []
    while (ano, mes) <= (ult_ano, ult_mes):
        saida.append({"mes": f"{mes:02d}/{ano}", "total": contagem.get((ano, mes), 0)})
        mes += 1
        if mes == 13:
            mes, ano = 1, ano + 1
    return saida


def _serie_mensal(qs, campo):
    pares = list(
        qs.annotate(mes=TruncMonth(campo))
        .values_list("mes")
        .annotate(total=Count("id"))
        .order_by("mes")  # sem order_by o gráfico embaralha
    )
    return _meses_contiguos(pares)


def _logins_por_dia(qs, inicio, fim):
    """Até 30 dias terminando em 'fim' (ou hoje)."""
    ref = fim or timezone.localdate()
    n = 30
    if inicio:
        n = max(1, min(30, (ref - inicio).days + 1))
    dias = [ref - timedelta(days=i) for i in range(n - 1, -1, -1)]
    contagem = dict(
        qs.filter(criado_em__date__gte=dias[0], criado_em__date__lte=dias[-1])
        .annotate(dia=TruncDate("criado_em"))
        .values_list("dia")
        .annotate(total=Count("id"))
        .order_by("dia")
    )
    return {
        "labels": [d.strftime("%d/%m") for d in dias],
        "valores": [contagem.get(d, 0) for d in dias],
    }


def _base_emprestimos(org, inicio, fim):
    return aplicar_periodo(
        Emprestimo.objects.filter(organizacao=org), "data_emprestimo", inicio, fim
    )


# ---------- métricas de UMA organização (dashboard e API usam esta função) ----------

def metricas_org(org, inicio=None, fim=None):
    hoje = date.today()
    base = _base_emprestimos(org, inicio, fim)
    exemplares = Exemplar.objects.filter(organizacao=org)
    reservas_abertas = Reserva.objects.filter(organizacao=org, atendida=False)

    # KPIs do período: UMA consulta (aggregate + Count com filter)
    kpis = base.aggregate(
        total=Count("id"),
        membros=Count("membro", distinct=True),
        abertos=Count("id", filter=Q(data_devolucao__isnull=True)),
    )
    # situação de agora: não depende do período
    atual = Emprestimo.objects.filter(
        organizacao=org, data_devolucao__isnull=True
    ).aggregate(
        abertos=Count("id"),
        atrasados=Count("id", filter=Q(data_prevista_devolucao__lt=hoje)),
    )

    por_status = dict(exemplares.values_list("status").annotate(n=Count("id")).order_by())
    total_exemplares = sum(por_status.values())
    emprestados = por_status.get("emprestado", 0)

    com_multa = Emprestimo.objects.filter(organizacao=org).filter(
        Q(data_devolucao__isnull=True, data_prevista_devolucao__lt=hoje)
        | Q(data_devolucao__gt=F("data_prevista_devolucao"))
    )
    multas_total = sum(e.valor_multa for e in com_multa)

    return {
        "kpis": kpis,
        "atual": atual,
        "acervo": {
            "titulos": Livro.objects.filter(organizacao=org).count(),
            "exemplares": total_exemplares,
            "ocupacao": round(100 * emprestados / total_exemplares) if total_exemplares else 0,
            "membros": Membro.objects.filter(organizacao=org).count(),
        },
        "multas_total": round(multas_total, 2),
        "reservas_fila": reservas_abertas.count(),
        "ranking_livros": _ranking(base, "exemplar__livro__titulo"),
        "ranking_autores": _ranking(base, "exemplar__livro__autor__nome"),
        "ranking_membros": _ranking(base, "membro__usuario__username"),
        "fila": _ranking(reservas_abertas, "livro__titulo"),
        "por_mes": _serie_mensal(base, "data_emprestimo"),
        "status": [
            {"status": nome, "total": por_status.get(cod, 0)}
            for cod, nome in STATUS_NOMES
        ],
    }


# ---------- dashboard do cliente ----------

@login_required
def dashboard_org(request):
    # superusuário sem Perfil não tem organização: vai para o painel admin
    if request.user.is_superuser and not hasattr(request.user, "perfil"):
        return redirect("dashboard_admin")

    org = org_atual(request)
    perfil = request.user.perfil
    form, inicio, fim = periodo_validado(request.GET)
    m = metricas_org(org, inicio, fim)
    base = _base_emprestimos(org, inicio, fim)
    hoje = date.today()

    lista_atrasados = (
        Emprestimo.objects.filter(
            organizacao=org,
            data_devolucao__isnull=True,
            data_prevista_devolucao__lt=hoje,
        )
        .select_related("exemplar__livro", "membro__usuario")
        .order_by("data_prevista_devolucao")[:8]
    )
    livros_parados = (
        Livro.objects.filter(organizacao=org)
        .exclude(pk__in=base.values("exemplar__livro_id"))
        .select_related("autor")
        .order_by("titulo")[:5]
    )

    contexto = {
        "org": org,
        "form": form,
        "periodo_qs": _periodo_qs(inicio, fim),
        "kpis": m["kpis"],
        "atual": m["atual"],
        "acervo": m["acervo"],
        "ocupacao": f"{m['acervo']['ocupacao']}%",
        "nota_abertos": f"{m['kpis']['abertos']} ainda em aberto",
        "multas": _moeda(m["multas_total"]),
        "reservas_fila": m["reservas_fila"],
        "ranking_livros": m["ranking_livros"],
        "ranking_autores": m["ranking_autores"],
        "ranking_membros": m["ranking_membros"],
        "fila": m["fila"],
        "lista_atrasados": lista_atrasados,
        "livros_parados": livros_parados,
        "graficos": {
            "status": {
                "labels": [s["status"] for s in m["status"]],
                "valores": [s["total"] for s in m["status"]],
            }
        },
        # dashboard por papel: operador vê KPIs e rankings, mas não séries nem exportação
        "mostra_series": perfil.eh_admin,
        "mostra_logins": perfil.eh_admin,
        "pode_exportar": perfil.eh_admin,
        "por_mes": m["por_mes"] if perfil.eh_admin else [],
    }

    if perfil.eh_admin:
        logins = RegistroLogin.objects.filter(organizacao=org)
        logins_periodo = aplicar_periodo(logins, "criado_em__date", inicio, fim)
        usuarios = logins_periodo.values("usuario").distinct().count()
        contexto.update(
            {
                "logins_periodo": logins_periodo.count(),
                "nota_logins": f"{usuarios} usuário(s) diferentes",
                "logins_hoje": logins.filter(criado_em__date=timezone.localdate()).count(),
                "top_usuarios": _ranking(logins_periodo, "usuario__username"),
            }
        )
        contexto["graficos"]["logins"] = _logins_por_dia(logins, inicio, fim)

    return render(request, "dashboard/org.html", contexto)


# ---------- dashboard do admin do sistema (todas as organizações) ----------

@superuser_required
def dashboard_admin(request):
    form, inicio, fim = periodo_validado(request.GET)
    agora = timezone.now()
    hoje = date.today()

    emp_qs = aplicar_periodo(Emprestimo.objects.all(), "data_emprestimo", inicio, fim)
    logins_qs = aplicar_periodo(RegistroLogin.objects.all(), "criado_em__date", inicio, fim)

    kpis = emp_qs.aggregate(
        total=Count("id"),
        membros=Count("membro", distinct=True),
        abertos=Count("id", filter=Q(data_devolucao__isnull=True)),
    )
    atual = Emprestimo.objects.filter(data_devolucao__isnull=True).aggregate(
        abertos=Count("id"),
        atrasados=Count("id", filter=Q(data_prevista_devolucao__lt=hoje)),
    )

    def por_org(qs):
        return dict(qs.values_list("organizacao_id").annotate(n=Count("id")).order_by())

    orgs = list(Organizacao.objects.order_by("nome"))
    usuarios = por_org(Perfil.objects.all())
    livros = por_org(Livro.objects.all())
    exemplares = por_org(Exemplar.objects.all())
    membros = por_org(Membro.objects.all())
    emp_org = por_org(emp_qs)
    log_org = por_org(logins_qs)
    ultimo = dict(
        RegistroLogin.objects.values_list("organizacao_id")
        .annotate(u=Max("criado_em"))
        .order_by()
    )

    limite = agora - timedelta(days=30)
    linhas = []
    for o in orgs:
        ult = ultimo.get(o.id)
        linhas.append(
            {
                "org": o,
                "usuarios": usuarios.get(o.id, 0),
                "livros": livros.get(o.id, 0),
                "exemplares": exemplares.get(o.id, 0),
                "membros": membros.get(o.id, 0),
                "emprestimos": emp_org.get(o.id, 0),
                "logins": log_org.get(o.id, 0),
                "ultimo_login": ult,
                "inativa": ult is None or ult < limite,
            }
        )
    linhas.sort(key=lambda l: (-l["emprestimos"], l["org"].nome))
    top_logins_org = sorted(linhas, key=lambda l: -l["logins"])[:8]

    por_status = dict(
        Exemplar.objects.values_list("status").annotate(n=Count("id")).order_by()
    )
    novas_orgs = _serie_mensal(
        aplicar_periodo(Organizacao.objects.all(), "criada_em__date", inicio, fim),
        "criada_em",
    )
    top_livros = [
        {"nome": f"{titulo} · {org}", "total": total}
        for titulo, org, total in emp_qs.values_list(
            "exemplar__livro__titulo", "organizacao__nome"
        )
        .annotate(total=Count("id"))
        .order_by("-total", "exemplar__livro__titulo")[:8]
    ]

    return render(
        request,
        "dashboard/admin.html",
        {
            "form": form,
            "periodo_qs": _periodo_qs(inicio, fim),
            "kpis": kpis,
            "atual": atual,
            "nota_abertos": f"{kpis['abertos']} ainda em aberto",
            "total_orgs": len(orgs),
            "orgs_inativas": sum(1 for l in linhas if l["inativa"]),
            "total_usuarios": sum(usuarios.values()),
            "total_titulos": sum(livros.values()),
            "total_exemplares": sum(exemplares.values()),
            "total_membros": sum(membros.values()),
            "logins_periodo": logins_qs.count(),
            "logins_hoje": RegistroLogin.objects.filter(
                criado_em__date=timezone.localdate()
            ).count(),
            "usuarios_logaram": logins_qs.values("usuario").distinct().count(),
            "linhas": linhas,
            "top_livros": top_livros,
            "ultimos_logins": RegistroLogin.objects.select_related(
                "usuario", "organizacao"
            ).order_by("-criado_em")[:10],
            "por_mes": _serie_mensal(emp_qs, "data_emprestimo"),
            "graficos": {
                "status": {
                    "labels": [nome for _, nome in STATUS_NOMES],
                    "valores": [por_status.get(cod, 0) for cod, _ in STATUS_NOMES],
                },
                "logins": _logins_por_dia(RegistroLogin.objects.all(), inicio, fim),
                "logins_orgs": {
                    "labels": [l["org"].nome for l in top_logins_org],
                    "valores": [l["logins"] for l in top_logins_org],
                },
                "novas_orgs": {
                    "labels": [d["mes"] for d in novas_orgs],
                    "valores": [d["total"] for d in novas_orgs],
                },
            },
        },
    )