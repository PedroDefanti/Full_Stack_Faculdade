from django.contrib import admin
from .models import Autor, Emprestimo, Exemplar, Livro, Membro, Reserva


@admin.register(Livro)
class LivroAdmin(admin.ModelAdmin):
    list_display = ("titulo", "autor", "ano", "organizacao")
    list_filter = ("organizacao",)


@admin.register(Autor)
class AutorAdmin(admin.ModelAdmin):
    list_display = ("nome", "organizacao")
    list_filter = ("organizacao",)


@admin.register(Membro)
class MembroAdmin(admin.ModelAdmin):
    list_display = ("usuario", "telefone", "organizacao")
    list_filter = ("organizacao",)


@admin.register(Exemplar)
class ExemplarAdmin(admin.ModelAdmin):
    list_display = ("codigo_patrimonio", "livro", "status", "organizacao")
    list_filter = ("organizacao", "status")


@admin.register(Emprestimo)
class EmprestimoAdmin(admin.ModelAdmin):
    list_display = ("exemplar", "membro", "data_emprestimo", "organizacao")
    list_filter = ("organizacao",)


@admin.register(Reserva)
class ReservaAdmin(admin.ModelAdmin):
    list_display = ("livro", "membro", "atendida", "organizacao")
    list_filter = ("organizacao", "atendida")