from django.urls import path
from . import views

urlpatterns = [
    # ------------------------------
    # Protected & Utility Views
    # ------------------------------
    # GET  /api/protegido/ → Vista protegida por Firebase
    path("protegido/", views.vista_protegida, name="vista_protegida"),
    # ------------------------------
    # User Registration & Profile
    # ------------------------------
    # POST /api/crear_usuario/ → Crear usuario en Firebase Auth y Firestore profile
    path("crear_usuario/", views.crear_usuario, name="crear_usuario"),
    # GET  /api/profile/<uid>/ → Perfil público de cualquier usuario
    path("profile/<str:uid>/", views.profile_detail, name="profile_detail"),
    # GET  /api/profile/       → Perfil propio + pets + posts + friends
    # POST /api/profile/       → Crear/Actualizar perfil propio
    path("profile/", views.profile, name="profile"),
    # GET  /api/profile_list/ → Listar perfiles públicos (admite ?q=)
    path("profile_list/", views.profile_list, name="profile_list"),
    # ------------------------------
    # Pets CRUD
    # ------------------------------
    # GET  /api/profile/pets/       → Listar mascotas
    # POST /api/profile/pets/       → Crear nueva mascota
    path("profile/pets/", views.pets, name="pets"),
    # PUT  /api/profile/pets/<pet_id>/    → Actualizar mascota
    # DELETE /api/profile/pets/<pet_id>/ → Eliminar mascota
    path("profile/pets/<str:pet_id>/", views.pet_detail, name="pet_detail"),
    # ------------------------------
    # Posts & Comments CRUD
    # ------------------------------
    # GET  /api/profile/posts/                  → Listar posts del usuario
    # POST /api/profile/posts/                  → Crear post con imagen
    path("profile/posts/", views.user_posts, name="user_posts"),
    # PUT    /api/profile/posts/<post_id>/      → Actualizar post
    # DELETE /api/profile/posts/<post_id>/      → Eliminar post
    path(
        "profile/posts/<str:post_id>/", views.user_post_detail, name="user_post_detail"
    ),
    # GET  /api/posts/<post_id>/comments/       → Listar comentarios de un post
    # POST /api/posts/<post_id>/comments/       → Crear comentario
    path("posts/<str:post_id>/comments/", views.comments, name="comments"),
    # PUT    /api/posts/<post_id>/comments/<comment_id>/ → Actualizar comentario
    # DELETE /api/posts/<post_id>/comments/<comment_id>/ → Eliminar comentario
    path(
        "posts/<str:post_id>/comments/<str:comment_id>/",
        views.comment_detail,
        name="comment_detail",
    ),
    # ------------------------------
    # Friends CRUD
    # ------------------------------
    # GET  /api/profile/friends/              → Listar amigos
    # POST /api/profile/friends/              → Agregar amigo bidireccional
    path("profile/friends/", views.friends, name="friends"),
    # GET    /api/profile/friends/<friend_uid>/ → Ver perfil de ese amigo
    # DELETE /api/profile/friends/<friend_uid>/ → Eliminar amigo
    path(
        "profile/friends/<str:friend_uid>/", views.friend_detail, name="friend_detail"
    ),
    # ------------------------------
    # Followers/Friends Relations CRUD
    # ------------------------------
    # GET  /api/profile/relations/           → Listar friends o followers según role
    # POST /api/profile/relations/           → Agregar friend/follower
    path("profile/relations/", views.relations, name="relations_list"),
    # DELETE /api/profile/relations/<other_uid>/ → Eliminar friend/follower
    path(
        "profile/relations/<str:other_uid>/", views.relations, name="relations_detail"
    ),
    # ------------------------------
    # Chat History
    # ------------------------------
    # GET /api/chat/<room>/history/ → Historial de chat desde base SQL
    path("chat/<str:room>/history/", views.chat_history, name="chat_history"),
]
