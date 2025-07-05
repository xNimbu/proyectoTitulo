from django.urls import path
from . import views

urlpatterns = [
    # ------------------------------
    # Protected & Utility Views
    # ------------------------------
    path("protegido/", views.vista_protegida, name="vista_protegida"),
    path("crear_usuario/", views.crear_usuario, name="crear_usuario"),
    path("login_google/", views.login_google, name="login_google"),

    # ------------------------------
    # User’s own profile, pets, posts, friends, relations
    # ------------------------------
    path("profile/", views.profile, name="profile"),
    path("profile_list/", views.profile_list, name="profile_list"),

    # Pets CRUD
    path("profile/pets/", views.pets, name="pets"),
    path("profile/pets/<str:pet_id>/", views.pet_detail, name="pet_detail"),

    # Posts CRUD
    path("profile/posts/", views.user_posts, name="user_posts"),
    path("profile/posts/<str:post_id>/", views.user_post_detail, name="user_post_detail"),

    # Comments on any post
    path("posts/<str:post_id>/comments/", views.comments, name="comments"),
    path("posts/<str:post_id>/comments/<str:comment_id>/", views.comment_detail, name="comment_detail"),
    path("posts/<str:post_id>/likes/", views.likes, name="likes"),

    # Friends CRUD
    path("profile/friends/", views.friends, name="friends"),
    path("profile/friends/<str:friend_uid>/", views.friend_detail, name="friend_detail"),

    # Relations (followers/friends)
    path("profile/relations/", views.relations, name="relations_list"),
    path("profile/relations/<str:other_uid>/", views.relations, name="relations_detail"),

    # Chat History
    path("chat/<str:room_name>/", views.chat_history, name="chat_history"),

    # ------------------------------
    # Public profile (dynamic) — ¡AL FINAL!
    # ------------------------------
    path("profile/<str:uid>/", views.profile_detail, name="profile_detail"),
]
