from django.db import models

# Create your models here.

class ChatMessage(models.Model):
    room = models.CharField(max_length=100)
    user = models.CharField(max_length=100)
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('timestamp',)