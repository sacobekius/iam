from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models import OneToOneField
from oauth2_provider.models import Application


class User(AbstractUser):
    applicatie = models.ForeignKey(Application, related_name='applicatie_users', on_delete=models.CASCADE, null=True, blank=True)
    personeelsnummer = models.CharField(max_length=6, null=True, blank=True)

class SyncPoint(models.Model):
    applicatie = OneToOneField(Application, related_name='applicatie_syncpoint', on_delete=models.CASCADE)
    url = models.URLField(max_length=255, blank=True, null=True)
    auth_token = models.CharField(max_length=255, blank=True, null=True)
    last_request = models.TextField(blank=True, null=True)
    last_request_body = models.TextField(blank=True, null=True)
    last_response = models.JSONField(blank=True, null=True)
    last_result = models.TextField(blank=True, null=True)
