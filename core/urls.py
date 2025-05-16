from django.urls import path
from . import views

urlpatterns = [
    # path("", hello_world, name="hello_world"),
    path("protegido/", views.vista_protegida, name="vista_protegida"),
    path("crear_usuario/", views.crear_usuario, name="crear_usuario"),
    path("profile/", views.profile),
    path("profile/pets/", views.pets),
    path("profile/pets/<str:pet_id>/", views.pet_detail),
]
