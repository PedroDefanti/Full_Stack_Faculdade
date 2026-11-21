from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.models import Organizacao, Perfil, RegistroLogin

from .models import Autor, Emprestimo, Exemplar, Livro, Membro


def criar_org(nome, username):
    org = Organizacao.objects.create(nome=nome)
    user = User.objects.create_user(username, password="x")
    Perfil.objects.create(usuario=user, organizacao=org)
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


class DashboardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org_a, cls.user_a = criar_org("A", "ua")
        cls.org_b, cls.user_b = criar_org("B", "ub")
        cls.root = User.objects.create_superuser("root", password="x")

    def test_login_gera_registro_com_a_organizacao(self):
        self.client.login(username="ua", password="x")
        self.assertEqual(
            RegistroLogin.objects.filter(
                usuario=self.user_a, organizacao=self.org_a
            ).count(),
            1,
        )

    def test_dashboard_do_cliente_so_mostra_a_propria_org(self):
        self.client.force_login(self.user_a)
        r = self.client.get(reverse("dashboard"))
        self.assertContains(r, "Livro A")
        self.assertNotContains(r, "Livro B")

    def test_cliente_nao_acessa_painel_admin(self):
        self.client.force_login(self.user_a)
        r = self.client.get(reverse("dashboard_admin"))
        self.assertEqual(r.status_code, 403)

    def test_anonimo_vai_para_login(self):
        r = self.client.get(reverse("dashboard_admin"))
        self.assertEqual(r.status_code, 302)

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
        r = self.client.post(
            reverse("login"), {"username": "root", "password": "x"}
        )
        self.assertRedirects(r, reverse("dashboard_admin"))