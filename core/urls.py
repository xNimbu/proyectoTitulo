from django.urls import path
from . import views
from .views import hello_world

urlpatterns = [
    path('', hello_world),
    path('protegido/', views.vista_protegida),
    path('crear_usuario/', views.crear_usuario),
]
