from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.models import Organizacao, Perfil

from .models import Autor, Exemplar, Livro


class IsolamentoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org_a = Organizacao.objects.create(nome="A")
        cls.org_b = Organizacao.objects.create(nome="B")
        cls.user_a = User.objects.create_user("ua", password="x")
        Perfil.objects.create(usuario=cls.user_a, organizacao=cls.org_a)

        cls.autor_a = Autor.objects.create(nome="Autor A", organizacao=cls.org_a)
        cls.autor_b = Autor.objects.create(nome="Autor B", organizacao=cls.org_b)
        cls.livro_a = Livro.objects.create(
            titulo="Livro A", autor=cls.autor_a, ano=2000, organizacao=cls.org_a
        )
        cls.livro_b = Livro.objects.create(
            titulo="Livro B", autor=cls.autor_b, ano=2000, organizacao=cls.org_b
        )

    def setUp(self):
        self.client.force_login(self.user_a)

    def test_lista_mostra_so_a_org_a(self):
        r = self.client.get(reverse("lista_livros"))
        self.assertContains(r, "Livro A")
        self.assertNotContains(r, "Livro B")

    def test_livro_de_outra_org_da_404(self):
        r = self.client.get(reverse("solicitar_livro", args=[self.livro_b.id]))
        self.assertEqual(r.status_code, 404)

    def test_livro_criado_fica_na_org_a(self):
        self.client.post(
            reverse("cadastrar_livro"),
            {"titulo": "Novo", "autor": self.autor_a.id, "ano": 2001},
        )
        self.assertEqual(Livro.objects.get(titulo="Novo").organizacao, self.org_a)

    def test_form_rejeita_autor_da_org_b(self):
        self.client.post(
            reverse("cadastrar_livro"),
            {"titulo": "Invasor", "autor": self.autor_b.id, "ano": 2001},
        )
        self.assertFalse(Livro.objects.filter(titulo="Invasor").exists())

    def test_codigo_repetido_em_outra_org_e_permitido(self):
        Exemplar.objects.create(
            livro=self.livro_b, codigo_patrimonio="T1", organizacao=self.org_b
        )
        self.client.post(
            reverse("cadastrar_exemplar"),
            {"livro_id": self.livro_a.id, "codigo_patrimonio": "T1"},
        )
        self.assertTrue(
            Exemplar.objects.filter(
                organizacao=self.org_a, codigo_patrimonio="T1"
            ).exists()
        )

    def test_api_lista_so_a_org_a(self):
        r = self.client.get("/api/livros/")
        titulos = [l["titulo"] for l in r.json()]
        self.assertEqual(titulos, ["Livro A"])

    def test_api_detalhe_de_outra_org_da_404(self):
        r = self.client.get(f"/api/livros/{self.livro_b.id}/")
        self.assertEqual(r.status_code, 404)