from django.contrib.auth.models import User
from django.db import models


class Organizacao(models.Model):
    nome = models.CharField(max_length=120)
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "organização"
        verbose_name_plural = "organizações"

    def __str__(self):
        return self.nome


class Perfil(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE)
    organizacao = models.ForeignKey(Organizacao, on_delete=models.PROTECT)

    def __str__(self):
        return f"{self.usuario.username} @ {self.organizacao}"


class DaOrganizacao(models.Model):
    organizacao = models.ForeignKey(
        Organizacao, on_delete=models.PROTECT, null=True  # TEMPORÁRIO (etapa 1)
    )

    class Meta:
        abstract = True
        
class RegistroLogin(models.Model):
    usuario = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="logins"
    )
    # sem organização para superusuário sem Perfil
    organizacao = models.ForeignKey(
        Organizacao,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="logins",
    )
    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)

    def __str__(self):
        return f"{self.usuario.username} em {self.criado_em:%d/%m/%Y %H:%M}"