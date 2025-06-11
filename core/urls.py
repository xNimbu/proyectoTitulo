from django.urls import path
from . import views

urlpatterns = [
    # path("", hello_world, name="hello_world"),
    path("protegido/", views.vista_protegida, name="vista_protegida"),
    path("crear_usuario/", views.crear_usuario, name="crear_usuario"),
    path("profile/", views.profile),
    path("profile/pets/", views.pets),
    path("profile/pets/<str:pet_id>/", views.pet_detail),
    path("profile_list/", views.profile_list, name="profile_list"),
    path("chat/<str:room>/history/", views.chat_history, name="chat_history"),
]
