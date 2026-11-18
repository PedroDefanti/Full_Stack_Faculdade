from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),                     # MUDOU: login/logout próprios
    path("api-auth/", include("rest_framework.urls")),
    path("api/", include("acervo.api_urls")),
    path("", include("acervo.urls")),
]