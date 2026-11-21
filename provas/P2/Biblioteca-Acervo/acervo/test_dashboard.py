from datetime import date

from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from core.models import Organizacao, Perfil, RegistroLogin

from .models import Autor, Emprestimo, Exemplar, Livro, Membro


def criar_org(nome, username, papel="admin"):
    org = Organizacao.objects.create(nome=nome)
    user = User.objects.create_user(username, password="x")
    Perfil.objects.create(usuario=user, organizacao=org, papel=papel)
    autor = Autor.objects.create(nome=f"Autor {nome}", organizacao=org)
    livro = Livro.objects.create(
        titulo=f"Livro {nome}", autor=autor, ano=2000, organizacao=org
    )
    exemplar = Exemplar.objects.create(
        livro=livro, codigo_patrimonio=f"{nome}1", organizacao=org,
        status="emprestado",
    )
    membro = Membro.objects.create(
        usuario=User.objects.create_user(f"membro{nome}", password="x"),
        organizacao=org,
    )
    Emprestimo.objects.create(
        exemplar=exemplar, membro=membro,
        data_prevista_devolucao=date.today(), organizacao=org,
    )
    return org, user


def emprestar(org, n):
    """Mais n empréstimos do livro/membro da organização."""
    livro = Livro.objects.filter(organizacao=org).first()
    membro = Membro.objects.filter(organizacao=org).first()
    base = Exemplar.objects.filter(organizacao=org).count()
    for i in range(n):
        ex = Exemplar.objects.create(
            livro=livro, codigo_patrimonio=f"{org.nome}x{base + i}",
            organizacao=org, status="emprestado",
        )
        Emprestimo.objects.create(
            exemplar=ex, membro=membro,
            data_prevista_devolucao=date.today(), organizacao=org,
        )


def novos_livros(org, n):
    autor = Autor.objects.filter(organizacao=org).first()
    total = Livro.objects.filter(organizacao=org).count()
    for i in range(n):
        livro = Livro.objects.create(
            titulo=f"Livro {org.nome} extra {total + i}", autor=autor,
            ano=2001, organizacao=org,
        )
        Exemplar.objects.create(
            livro=livro, codigo_patrimonio=f"{org.nome}e{total + i}",
            organizacao=org,
        )


class DashboardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org_a, cls.user_a = criar_org("A", "ua")
        cls.org_b, cls.user_b = criar_org("B", "ub")
        emprestar(cls.org_a, 2)   # org A: 3 empréstimos
        emprestar(cls.org_b, 4)   # org B: 5 empréstimos
        cls.op = User.objects.create_user("op", password="x")
        Perfil.objects.create(usuario=cls.op, organizacao=cls.org_a, papel="operador")
        cls.root = User.objects.create_superuser("root", password="x")

    # ----- métricas -----
    def test_total_da_organizacao(self):
        self.client.force_login(self.user_a)
        r = self.client.get(reverse("dashboard"))
        self.assertEqual(r.context["kpis"]["total"], 3)
        self.client.force_login(self.user_b)
        r = self.client.get(reverse("dashboard"))
        self.assertEqual(r.context["kpis"]["total"], 5)

    def test_periodo_filtra_e_serie_sai_em_ordem(self):
        pks = list(
            Emprestimo.objects.filter(organizacao=self.org_a)
            .order_by("pk").values_list("pk", flat=True)
        )
        datas = [date(2020, 1, 15), date(2020, 2, 15), date(2020, 3, 15)]
        for pk, dia in zip(pks, datas):
            Emprestimo.objects.filter(pk=pk).update(data_emprestimo=dia)

        self.client.force_login(self.user_a)
        r = self.client.get(reverse("dashboard"), {"inicio": "2020-02-01", "fim": "2020-03-31"})
        self.assertEqual(r.context["kpis"]["total"], 2)
        self.assertEqual(
            r.context["por_mes"],
            [{"mes": "02/2020", "total": 1}, {"mes": "03/2020", "total": 1}],
        )
        r = self.client.get(reverse("dashboard"), {"inicio": "2020-01-01"})
        self.assertEqual(r.context["kpis"]["total"], 3)

    def test_data_invalida_nao_gera_erro_500(self):
        self.client.force_login(self.user_a)
        r = self.client.get(reverse("dashboard"), {"inicio": "abc"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["kpis"]["total"], 3)  # filtro ignorado

    def test_inicio_maior_que_fim_mostra_erro(self):
        self.client.force_login(self.user_a)
        r = self.client.get(reverse("dashboard"), {"inicio": "2020-03-01", "fim": "2020-01-01"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "não pode ser maior")

    def test_dashboard_vazio_sem_erro(self):
        org = Organizacao.objects.create(nome="Vazia")
        user = User.objects.create_user("vazio", password="x")
        Perfil.objects.create(usuario=user, organizacao=org, papel="admin")
        self.client.force_login(user)
        r = self.client.get(reverse("dashboard"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["kpis"]["total"], 0)
        self.assertContains(r, "Sem dados")

    # ----- isolamento -----
    def test_dashboard_do_cliente_so_mostra_a_propria_org(self):
        self.client.force_login(self.user_a)
        r = self.client.get(reverse("dashboard"))
        self.assertContains(r, "Livro A")
        self.assertNotContains(r, "Livro B")

    # ----- papéis -----
    def test_operador_nao_ve_series_nem_exporta(self):
        self.client.force_login(self.op)
        r = self.client.get(reverse("dashboard"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["kpis"]["total"], 3)   # KPIs: sim
        self.assertFalse(r.context["mostra_series"])      # séries: não
        self.assertEqual(r.context["por_mes"], [])
        self.assertNotContains(r, "Exportar")
        r = self.client.get(reverse("exportar", args=["acervo", "csv"]))
        self.assertEqual(r.status_code, 403)              # exportação: não

    def test_administrador_ve_series_e_exporta(self):
        self.client.force_login(self.user_a)
        r = self.client.get(reverse("dashboard"))
        self.assertTrue(r.context["mostra_series"])
        self.assertContains(r, "Exportar")
        r = self.client.get(reverse("exportar", args=["acervo", "csv"]))
        self.assertEqual(r.status_code, 200)

    # ----- API -----
    def test_api_dashboard_do_administrador(self):
        self.client.force_login(self.user_a)
        r = self.client.get("/api/dashboard/")
        self.assertEqual(r.status_code, 200)
        dados = r.json()
        self.assertEqual(dados["kpis"]["total"], 3)
        self.assertIn("por_mes", dados)
        self.assertNotIn("Livro B", str(dados))

    def test_api_dashboard_do_operador_sem_serie(self):
        self.client.force_login(self.op)
        dados = self.client.get("/api/dashboard/").json()
        self.assertEqual(dados["kpis"]["total"], 3)
        self.assertNotIn("por_mes", dados)

    def test_api_dashboard_exige_login(self):
        r = self.client.get("/api/dashboard/")
        self.assertIn(r.status_code, (401, 403))

    def test_api_dashboard_periodo_invalido_da_400(self):
        self.client.force_login(self.user_a)
        r = self.client.get("/api/dashboard/", {"inicio": "abc"})
        self.assertEqual(r.status_code, 400)

    # ----- login e painel admin (já existiam) -----
    def test_login_gera_registro_com_a_organizacao(self):
        self.client.login(username="ua", password="x")
        self.assertEqual(
            RegistroLogin.objects.filter(usuario=self.user_a, organizacao=self.org_a).count(),
            1,
        )

    def test_cliente_nao_acessa_painel_admin(self):
        self.client.force_login(self.user_a)
        self.assertEqual(self.client.get(reverse("dashboard_admin")).status_code, 403)

    def test_anonimo_vai_para_login(self):
        self.assertEqual(self.client.get(reverse("dashboard_admin")).status_code, 302)

    def test_superusuario_ve_todas_as_orgs(self):
        self.client.force_login(self.root)
        r = self.client.get(reverse("dashboard_admin"))
        self.assertContains(r, "Livro A")
        self.assertContains(r, "Livro B")

    def test_superusuario_sem_perfil_e_redirecionado_ao_painel_admin(self):
        self.client.force_login(self.root)
        r = self.client.get(reverse("dashboard"))
        self.assertRedirects(r, reverse("dashboard_admin"))

    def test_superusuario_loga_pela_tela_e_cai_no_painel_admin(self):
        r = self.client.post(reverse("login"), {"username": "root", "password": "x"})
        self.assertRedirects(r, reverse("dashboard_admin"))


class ConsultasTests(TestCase):
    """N+1: o número de consultas não pode crescer com o volume de dados."""

    @classmethod
    def setUpTestData(cls):
        cls.org, cls.user = criar_org("A", "ua")

    def contar(self, nome):
        with CaptureQueriesContext(connection) as ctx:
            r = self.client.get(reverse(nome))
        self.assertEqual(r.status_code, 200)
        return len(ctx)

    def test_consultas_nao_crescem_com_o_volume(self):
        self.client.force_login(self.user)
        for nome in ["lista_livros", "lista_emprestimos", "buscar_livro", "dashboard"]:
            antes = self.contar(nome)
            novos_livros(self.org, 5)
            emprestar(self.org, 5)
            self.assertEqual(self.contar(nome), antes, nome)

    def test_listagem_de_emprestimos_com_select_related(self):
        # no estilo do slide 31: 1 consulta, independente de N
        with self.assertNumQueries(1):
            for e in Emprestimo.objects.select_related("exemplar__livro", "membro__usuario"):
                e.exemplar.livro.titulo
                e.membro.usuario.username