from django.urls import path

from .api_views import LivroDetail, LivroListCreate

urlpatterns = [
    path("livros/", LivroListCreate.as_view()),
    path("livros/<int:pk>/", LivroDetail.as_view()),
]