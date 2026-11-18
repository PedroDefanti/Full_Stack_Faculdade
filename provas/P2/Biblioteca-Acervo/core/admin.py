from django.contrib import admin
from .models import Organizacao, Perfil

admin.site.register(Organizacao)


@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    list_display = ("usuario", "organizacao")
    list_filter = ("organizacao",)