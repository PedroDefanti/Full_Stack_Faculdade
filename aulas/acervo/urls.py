from django.urls import path
from . import views

urlpatterns = [
    path('', views.lista_livros, name='lista'),
    path('busca/', views.buscar_acervo, name='buscar_acervo'),  
    path('novo_livro/', views.novo_livro, name='novo_livro'),
]