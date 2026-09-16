from django.urls import path
from . import views

urlpatterns = [
    path("", views.lista_livros, name="lista_livros"),
    path(
        "solicitar/<int:livro_id>/",
        views.solicitar_livro,
        name="solicitar_livro",
    ),
    path(
        "reservas/<int:livro_id>/", views.fila_reservas, name="fila_reservas"
    ),
    path("emprestimos/", views.lista_emprestimos, name="lista_emprestimos"),
    path(
        "devolver/<int:emprestimo_id>/",
        views.devolver_livro,
        name="devolver_livro",
    ),
    path("autor/novo/", views.cadastrar_autor, name="cadastrar_autor"),
    path("livro/novo/", views.cadastrar_livro, name="cadastrar_livro"),
    path(
        "exemplar/novo/", views.cadastrar_exemplar, name="cadastrar_exemplar"
    ),
    path(
        "exemplar/novo/<int:livro_id>/",
        views.cadastrar_exemplar,
        name="cadastrar_exemplar",
    ),
    path("membro/novo/", views.cadastrar_membro, name="cadastrar_membro"),
]