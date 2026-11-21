from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Autor, Livro
from .test_dashboard import criar_org


class ExportacaoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org_a, cls.user_a = criar_org("A", "ua")
        cls.org_b, cls.user_b = criar_org("B", "ub")
        cls.root = User.objects.create_superuser("root", password="x")

    def baixar(self, user, nome, recurso, formato="csv"):
        self.client.force_login(user)
        return self.client.get(reverse(nome, args=[recurso, formato]))

    def test_csv_do_cliente_so_tem_a_propria_org(self):
        r = self.baixar(self.user_a, "exportar", "acervo")
        self.assertEqual(r.status_code, 200)
        self.assertIn("attachment", r["Content-Disposition"])
        self.assertTrue(r.content.startswith(b"\xef\xbb\xbf"))  # BOM
        corpo = r.content.decode("utf-8")
        self.assertIn("Livro A", corpo)
        self.assertNotIn("Livro B", corpo)

    def test_emprestimos_nao_vazam_membros_de_outra_org(self):
        corpo = self.baixar(self.user_a, "exportar", "emprestimos").content.decode()
        self.assertIn("membroA", corpo)
        self.assertNotIn("membroB", corpo)

    def test_json_do_cliente(self):
        r = self.baixar(self.user_a, "exportar", "acervo", "json")
        titulos = [l["Título"] for l in r.json()]
        self.assertEqual(titulos, ["Livro A"])

    def test_xlsx_do_cliente(self):
        try:
            import openpyxl  # noqa: F401
        except ImportError:
            self.skipTest("openpyxl não instalado")
        r = self.baixar(self.user_a, "exportar", "acervo", "xlsx")
        self.assertEqual(r.status_code, 200)
        self.assertIn("spreadsheetml", r["Content-Type"])
        self.assertTrue(r.content.startswith(b"PK"))  # xlsx é um zip

    def test_csv_neutraliza_formulas(self):
        autor = Autor.objects.get(nome="Autor A")
        Livro.objects.create(
            titulo="=1+1", autor=autor, ano=2000, organizacao=self.org_a
        )
        corpo = self.baixar(self.user_a, "exportar", "acervo").content.decode()
        self.assertIn("'=1+1", corpo)

    def test_formato_ou_recurso_invalido_da_404(self):
        self.assertEqual(self.baixar(self.user_a, "exportar", "acervo", "pdf").status_code, 404)
        self.assertEqual(self.baixar(self.user_a, "exportar", "segredos").status_code, 404)

    def test_cliente_nao_exporta_dados_do_admin(self):
        r = self.baixar(self.user_a, "exportar_admin", "organizacoes")
        self.assertEqual(r.status_code, 403)

    def test_admin_exporta_todas_as_orgs(self):
        corpo = self.baixar(self.root, "exportar_admin", "emprestimos").content.decode()
        self.assertIn("Livro A", corpo)
        self.assertIn("Livro B", corpo)

    def test_admin_organizacoes_csv(self):
        r = self.baixar(self.root, "exportar_admin", "organizacoes")
        self.assertEqual(r.status_code, 200)