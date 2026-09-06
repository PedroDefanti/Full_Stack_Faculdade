from django.db import models
from localflavor.br.validators import BRCPFValidator
from django.contrib.auth.models import AbstractUser



# Create your models here.
"""
paciente precisa ter:
nome
email
telefone
cpf
"""

class Paciente(AbstractUser):
    telefone = models.CharField(max_length=15)
    cpf = models.CharField(unique=True,validators=[BRCPFValidator()],max_length=14)

    def __str__(self):
        return self.nome
