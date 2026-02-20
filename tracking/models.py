from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class TrackingSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    mode = models.CharField(max_length=20, default="bike")

    locations = models.JSONField(default=list)

    total_distance = models.FloatField(default=0)  
    total_time = models.FloatField(default=0)      

    last_lat = models.FloatField(null=True, blank=True)
    last_lng = models.FloatField(null=True, blank=True)
    last_timestamp = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - Session {self.id}"
