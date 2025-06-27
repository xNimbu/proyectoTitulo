"""
URL configuration for backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('core.urls')),
    path('chat_prueba/', TemplateView.as_view(template_name='chat_prueba.html'), name='chat_prueba'),
    path('chat_prueba_users/', TemplateView.as_view(template_name='chat_prueba_users.html'), name='chat_prueba_users'),
    path('token/', TemplateView.as_view(template_name='token.html'), name='token'),
    path('ver-posts/', TemplateView.as_view(template_name='ver-posts.html'), name='ver-posts'),
]
