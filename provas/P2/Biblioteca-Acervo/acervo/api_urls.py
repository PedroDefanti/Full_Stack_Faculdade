from django.urls import path

from .api_views import DashboardApi, LivroDetail, LivroListCreate

urlpatterns = [
    path("livros/", LivroListCreate.as_view()),
    path("livros/<int:pk>/", LivroDetail.as_view()),
    path("dashboard/", DashboardApi.as_view()),  # NOVO: /api/dashboard/?inicio=&fim=
]