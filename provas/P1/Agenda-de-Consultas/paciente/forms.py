from .models import Paciente
from django.contrib.auth.forms import UserCreationForm
from django import forms

class PacienteForm(UserCreationForm):
    class Meta:
        model = Paciente
        fields = ['username',"email","telefone","cpf"]
        
    