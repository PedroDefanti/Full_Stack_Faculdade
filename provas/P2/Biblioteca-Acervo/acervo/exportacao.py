import csv
from datetime import date, datetime
from io import BytesIO

from django.db.models import Count, Max, Q
from django.http import Http404, HttpResponse, JsonResponse
from django.utils import timezone
from django.utils.text import slugify

from core.models import Organizacao, Perfil, RegistroLogin
from core.utils import org_atual, papel_requerido

from .dashboard import superuser_required
from .forms import aplicar_periodo, periodo_validado
from .models import Emprestimo, Exemplar, Livro, Membro, Reserva

FORMATOS = {"csv", "xlsx", "json"}
PERIGOSOS = ("=", "+", "-", "@", "\t", "\r")


# ---------- formatação e geração de arquivos ----------

def _periodo(request):  # MUDOU: inicio/fim validados pelo PeriodoForm
    _, inicio, fim = periodo_validado(request.GET)
    return inicio, fim


def _valor(v, formato):
    if v is None:
        return ""
    if isinstance(v, datetime):  # datetime vem antes de date (é subclasse)
        if timezone.is_aware(v):
            v = timezone.localtime(v)
        return v.isoformat(timespec="minutes") if formato == "json" else v.strftime("%d/%m/%Y %H:%M")
    if isinstance(v, date):
        return v.isoformat() if formato == "json" else v.strftime("%d/%m/%Y")
    if isinstance(v, bool):
        return v if formato == "json" else ("Sim" if v else "Não")
    if isinstance(v, float):
        return round(v, 2) if formato != "csv" else f"{v:.2f}".replace(".", ",")
    return v


def _seguro(v):
    """Neutraliza 'injeção de fórmula' (= + - @) em textos digitados por usuários."""
    if isinstance(v, str) and v.startswith(PERIGOSOS):
        return "'" + v
    return v


def _csv(arquivo, cabecalho, linhas):
    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="{arquivo}.csv"'
    resp.write("\ufeff")  # BOM: o Excel abre com os acentos corretos
    escritor = csv.writer(resp, delimiter=";")  # padrão do Excel no Brasil
    escritor.writerow(cabecalho)
    for linha in linhas:
        escritor.writerow([_seguro(_valor(c, "csv")) for c in linha])
    return resp


def _xlsx(arquivo, cabecalho, linhas):
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill
        from openpyxl.utils import get_column_letter
    except ImportError:
        return HttpResponse(
            "Exportação para Excel indisponível: instale o openpyxl (pip install openpyxl).",
            status=501,
            content_type="text/plain; charset=utf-8",
        )

    wb = Workbook()
    ws = wb.active
    ws.title = "Dados"
    ws.append(cabecalho)
    for celula in ws[1]:
        celula.font = Font(bold=True, color="FFFFFF")
        celula.fill = PatternFill("solid", fgColor="4F46E5")
    for linha in linhas:
        ws.append([_seguro(_valor(c, "xlsx")) for c in linha])
    ws.freeze_panes = "A2"

    for i, titulo in enumerate(cabecalho, start=1):
        maior = len(str(titulo))
        for r in range(2, min(ws.max_row, 200) + 1):
            maior = max(maior, len(str(ws.cell(row=r, column=i).value or "")))
        ws.column_dimensions[get_column_letter(i)].width = min(maior + 2, 50)

    buffer = BytesIO()
    wb.save(buffer)
    resp = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resp["Content-Disposition"] = f'attachment; filename="{arquivo}.xlsx"'
    return resp


def _json(arquivo, cabecalho, linhas):
    dados = [
        dict(zip(cabecalho, [_valor(c, "json") for c in linha])) for linha in linhas
    ]
    resp = JsonResponse(
        dados, safe=False, json_dumps_params={"ensure_ascii": False, "indent": 2}
    )
    resp["Content-Disposition"] = f'attachment; filename="{arquivo}.json"'
    return resp


def _resposta(formato, nome_base, cabecalho, linhas):
    arquivo = f"{nome_base}_{date.today():%Y%m%d}"
    return {"csv": _csv, "xlsx": _xlsx, "json": _json}[formato](
        arquivo, cabecalho, linhas
    )


# ---------- conjuntos de dados do CLIENTE (sempre filtrados por org) ----------

CAB_EMPRESTIMOS = [
    "Livro", "Código de patrimônio", "Membro", "Data do empréstimo",
    "Devolução prevista", "Data da devolução", "Dias de atraso",
    "Multa (R$)", "Situação",
]


def _situacao(e, hoje):
    if e.data_devolucao:
        return "Devolvido com atraso" if e.dias_atraso else "Devolvido"
    return "Atrasado" if e.data_prevista_devolucao < hoje else "Em aberto"


def _linha_emprestimo(e, hoje):
    return [
        e.exemplar.livro.titulo,
        e.exemplar.codigo_patrimonio,
        e.membro.usuario.username,
        e.data_emprestimo,
        e.data_prevista_devolucao,
        e.data_devolucao,
        e.dias_atraso,
        e.valor_multa,
        _situacao(e, hoje),
    ]


def _acervo(org, periodo):
    qs = (
        Livro.objects.filter(organizacao=org)
        .select_related("autor")
        .annotate(
            total=Count("exemplares"),
            disp=Count("exemplares", filter=Q(exemplares__status="disponivel")),
            emp=Count("exemplares", filter=Q(exemplares__status="emprestado")),
            man=Count("exemplares", filter=Q(exemplares__status="manutencao")),
        )
        .order_by("titulo")
    )
    cab = ["Título", "Autor", "Ano", "Exemplares", "Disponíveis", "Emprestados", "Em manutenção"]
    return cab, ([l.titulo, l.autor.nome, l.ano, l.total, l.disp, l.emp, l.man] for l in qs)


def _emprestimos(org, periodo):
    qs = aplicar_periodo(
        Emprestimo.objects.filter(organizacao=org), "data_emprestimo", *periodo
    )
    qs = qs.select_related("exemplar__livro", "membro__usuario").order_by(
        "-data_emprestimo", "-id"
    )
    hoje = date.today()
    return CAB_EMPRESTIMOS, (_linha_emprestimo(e, hoje) for e in qs)


def _atrasos(org, periodo):
    qs = (
        Emprestimo.objects.filter(
            organizacao=org,
            data_devolucao__isnull=True,
            data_prevista_devolucao__lt=date.today(),
        )
        .select_related("exemplar__livro", "membro__usuario")
        .order_by("data_prevista_devolucao")
    )
    cab = [
        "Livro", "Código de patrimônio", "Membro", "Telefone",
        "Devolução prevista", "Dias de atraso", "Multa (R$)",
    ]
    return cab, (
        [
            e.exemplar.livro.titulo,
            e.exemplar.codigo_patrimonio,
            e.membro.usuario.username,
            e.membro.telefone,
            e.data_prevista_devolucao,
            e.dias_atraso,
            e.valor_multa,
        ]
        for e in qs
    )


def _membros(org, periodo):
    qs = (
        Membro.objects.filter(organizacao=org)
        .select_related("usuario")
        .annotate(
            total=Count("emprestimo", distinct=True),
            abertos=Count(
                "emprestimo",
                filter=Q(emprestimo__data_devolucao__isnull=True),
                distinct=True,
            ),
            fila=Count("reserva", filter=Q(reserva__atendida=False), distinct=True),
        )
        .order_by("usuario__username")
    )
    cab = ["Usuário", "Telefone", "Empréstimos (total)", "Empréstimos em aberto", "Reservas na fila"]
    return cab, ([m.usuario.username, m.telefone, m.total, m.abertos, m.fila] for m in qs)


def _reservas(org, periodo):
    qs = (
        Reserva.objects.filter(organizacao=org)
        .select_related("livro", "membro__usuario")
        .order_by("-data_reserva")
    )
    cab = ["Livro", "Membro", "Data da reserva", "Atendida"]
    return cab, (
        [r.livro.titulo, r.membro.usuario.username, r.data_reserva, r.atendida]
        for r in qs
    )


def _logins(org, periodo):
    qs = aplicar_periodo(
        RegistroLogin.objects.filter(organizacao=org), "criado_em__date", *periodo
    )
    qs = qs.select_related("usuario").order_by("-criado_em")
    return ["Usuário", "Data e hora"], ([r.usuario.username, r.criado_em] for r in qs)


def _ranking_livros(org, periodo):
    qs = aplicar_periodo(
        Emprestimo.objects.filter(organizacao=org), "data_emprestimo", *periodo
    )
    qs = (
        qs.values_list("exemplar__livro__titulo", "exemplar__livro__autor__nome")
        .annotate(total=Count("id"))
        .order_by("-total", "exemplar__livro__titulo")
    )
    return ["Posição", "Livro", "Autor", "Empréstimos"], (
        [pos, titulo, autor, total]
        for pos, (titulo, autor, total) in enumerate(qs, start=1)
    )


RECURSOS_ORG = {
    "acervo": _acervo,
    "emprestimos": _emprestimos,
    "atrasos": _atrasos,
    "membros": _membros,
    "reservas": _reservas,
    "logins": _logins,
    "ranking-livros": _ranking_livros,
}


# ---------- conjuntos de dados do ADMIN (globais de propósito) ----------

def _admin_organizacoes(periodo):
    def por_org(qs):
        return dict(
            qs.values_list("organizacao_id").annotate(n=Count("id")).order_by()
        )

    emprestimos = aplicar_periodo(Emprestimo.objects.all(), "data_emprestimo", *periodo)
    logins = aplicar_periodo(RegistroLogin.objects.all(), "criado_em__date", *periodo)

    usuarios = por_org(Perfil.objects.all())
    livros = por_org(Livro.objects.all())
    exemplares = por_org(Exemplar.objects.all())
    membros = por_org(Membro.objects.all())
    emp = por_org(emprestimos)
    log = por_org(logins)
    ultimo = dict(
        RegistroLogin.objects.values_list("organizacao_id")
        .annotate(u=Max("criado_em"))
        .order_by()
    )

    sufixo = "no período" if any(periodo) else "total"
    cab = [
        "Organização", "Criada em", "Usuários", "Títulos", "Exemplares",
        "Membros", f"Empréstimos ({sufixo})", f"Logins ({sufixo})", "Último login",
    ]
    linhas = (
        [
            o.nome, o.criada_em, usuarios.get(o.id, 0), livros.get(o.id, 0),
            exemplares.get(o.id, 0), membros.get(o.id, 0), emp.get(o.id, 0),
            log.get(o.id, 0), ultimo.get(o.id),
        ]
        for o in Organizacao.objects.order_by("nome")
    )
    return cab, linhas


def _admin_usuarios(periodo):
    qs = (
        Perfil.objects.select_related("usuario", "organizacao")
        .annotate(n=Count("usuario__logins"), ultimo=Max("usuario__logins__criado_em"))
        .order_by("organizacao__nome", "usuario__username")
    )
    cab = ["Usuário", "Organização", "Papel", "Total de logins", "Último login"]
    return cab, (
        [p.usuario.username, p.organizacao.nome, p.get_papel_display(), p.n, p.ultimo]
        for p in qs
    )


def _admin_emprestimos(periodo):
    qs = aplicar_periodo(Emprestimo.objects.all(), "data_emprestimo", *periodo)
    qs = qs.select_related(
        "organizacao", "exemplar__livro", "membro__usuario"
    ).order_by("-data_emprestimo", "-id")
    hoje = date.today()
    return ["Organização"] + CAB_EMPRESTIMOS, (
        [e.organizacao.nome] + _linha_emprestimo(e, hoje) for e in qs
    )


def _admin_logins(periodo):
    qs = aplicar_periodo(RegistroLogin.objects.all(), "criado_em__date", *periodo)
    qs = qs.select_related("usuario", "organizacao").order_by("-criado_em")
    return ["Usuário", "Organização", "Data e hora"], (
        [r.usuario.username, r.organizacao.nome if r.organizacao else "", r.criado_em]
        for r in qs
    )


RECURSOS_ADMIN = {
    "organizacoes": _admin_organizacoes,
    "usuarios": _admin_usuarios,
    "emprestimos": _admin_emprestimos,
    "logins": _admin_logins,
}


# ---------- views ----------

def _responder(request, recurso, formato, registro, nome_base, *args):
    if formato not in FORMATOS or recurso not in registro:
        raise Http404
    cabecalho, linhas = registro[recurso](*args, _periodo(request))
    return _resposta(formato, f"{nome_base}-{recurso}", cabecalho, linhas)


@papel_requerido("admin")  # MUDOU: operador não exporta
def exportar_org(request, recurso, formato):
    org = org_atual(request)
    return _responder(
        request, recurso, formato, RECURSOS_ORG, slugify(org.nome) or "org", org
    )


@superuser_required
def exportar_admin(request, recurso, formato):
    return _responder(request, recurso, formato, RECURSOS_ADMIN, "admin")