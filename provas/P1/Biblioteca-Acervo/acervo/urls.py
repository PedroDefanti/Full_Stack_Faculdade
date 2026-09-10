from django.urls import path
from . import views


urlpatterns = [
    path('inicio', views.inicio),
    path('',views.lista_livros,name='lista'),
    path('novo/',views.novo_livro,name="novo"),
    path('editar/<int:id>/',views.editar_livro,name="editar"),
    path('remover/<int:id>/',views.remover_livro,name="remover"),

]