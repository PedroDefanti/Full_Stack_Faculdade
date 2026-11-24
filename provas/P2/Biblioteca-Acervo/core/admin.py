from django.contrib import admin
from .models import Organizacao, Perfil, RegistroLogin

admin.site.register(Organizacao)


@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    list_display = ("usuario", "organizacao", "papel")
    list_filter = ("organizacao", "papel")
@admin.register(RegistroLogin)
class RegistroLoginAdmin(admin.ModelAdmin):
    list_display = ("usuario", "organizacao", "criado_em")
    list_filter = ("organizacao",)