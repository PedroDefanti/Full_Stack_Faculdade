from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Organizacao, Perfil


class RegistroTests(TestCase):
    dados = {
        "username": "maria",
        "organizacao": "Biblioteca da Maria",
        "password1": "senha-forte-123",
        "password2": "senha-forte-123",
    }

    def test_registro_cria_usuario_organizacao_e_perfil(self):
        r = self.client.post(reverse("registro"), self.dados)
        self.assertRedirects(r, reverse("lista_livros"))
        user = User.objects.get(username="maria")
        self.assertEqual(user.perfil.organizacao.nome, "Biblioteca da Maria")

    def test_cada_registro_gera_organizacao_propria(self):
        self.client.post(reverse("registro"), self.dados)
        self.client.logout()
        self.client.post(
            reverse("registro"),
            {**self.dados, "username": "joao", "organizacao": "Biblioteca do João"},
        )
        self.assertEqual(Organizacao.objects.count(), 2)
        self.assertNotEqual(
            User.objects.get(username="maria").perfil.organizacao,
            User.objects.get(username="joao").perfil.organizacao,
        )

    def test_username_repetido_e_rejeitado_sem_criar_nada(self):
        User.objects.create_user("maria", password="x")
        self.client.post(reverse("registro"), self.dados)
        self.assertEqual(Organizacao.objects.count(), 0)
        self.assertEqual(Perfil.objects.count(), 0)