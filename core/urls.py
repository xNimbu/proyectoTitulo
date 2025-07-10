from django.urls import path
from . import views

urlpatterns = [
    # ------------------------------
    # Protected & Utility Views
    # ------------------------------
    path("protegido/", views.vista_protegida, name="vista_protegida"),
    path("crear_usuario/", views.crear_usuario, name="crear_usuario"),
    path("login_google/", views.login_google, name="login_google"),
    path("admin/create_service_profile/", views.create_service_profile, name="create_service_profile"),
    path("services_list/", views.services_list, name="services_list"),
    path("contact_service/", views.contact_service, name="contact_service"),

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
    path("profile/posts/user/<str:uid>/", views.posts_by_user, name="posts_by_user"),

    # Posts from user and friends
    path("profile/friends/posts/", views.friends_posts, name="friends_posts"),

    # Comments on any post
    path("posts/<str:post_id>/comments/", views.comments, name="comments"),
    path("posts/<str:post_id>/comments/<str:comment_id>/", views.comment_detail, name="comment_detail"),
    path("posts/<str:post_id>/likes/", views.likes, name="likes"),

    # Notifications
    path("profile/notifications/", views.notifications, name="notifications"),
    path(
        "profile/notifications/<str:notification_id>/",
        views.notification_detail,
        name="notification_detail",
    ),

    # Friends CRUD
    path("profile/friends/", views.friends, name="friends"),
    path("profile/friends/<str:friend_uid>/", views.friend_detail, name="friend_detail"),

    # Relations (followers/friends)
    path("profile/relations/", views.relations, name="relations_list"),
    path("profile/relations/<str:other_uid>/", views.relations, name="relations_detail"),

    # Chat History
    path("chat/<str:room_name>/", views.chat_history, name="chat_history"),
    path("chat/<str:room_name>/unread/", views.chat_unread_count, name="chat_unread_count"),

    # ------------------------------
    # Public profile (dynamic) — ¡AL FINAL!
    # ------------------------------
    path(
        "profile/username/<str:username>/",
        views.profile_by_username,
        name="profile_by_username",
    ),
    path("profile/<str:uid>/", views.profile_detail, name="profile_detail"),
]
