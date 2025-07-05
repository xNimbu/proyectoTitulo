from django.db import models

# Create your models here.

class ChatMessage(models.Model):
    room    = models.CharField(max_length=100)
    user    = models.CharField(max_length=100)
    message = models.TextField()
    created = models.DateTimeField(auto_now_add=True)
    read_by = models.JSONField(default=list)

    def __str__(self):
        return f'[{self.created:%Y-%m-%d %H:%M}] {self.user}: {self.message}'