from django.db import models
from django.contrib.auth.models import AbstractUser, Group
from oauth2_provider.models import Application

class LocGroup(models.Model):
    applicatie = models.ForeignKey("oauth2_provider.Application", related_name='applicatie_groups', on_delete=models.CASCADE, null=True,
                                   blank=True)
    name = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return self.name


class User(AbstractUser):
    applicatie = models.ForeignKey("oauth2_provider.Application", related_name='applicatie_users', on_delete=models.CASCADE, null=True,
                                   blank=True)
    personeelsnummer = models.CharField(max_length=6, null=True, blank=True)
    locgroup = models.ManyToManyField(LocGroup, related_name='user_set', blank=True)


class SyncPoint(models.Model):
    applicatie = models.OneToOneField("oauth2_provider.Application", related_name='applicatie_syncpoint', on_delete=models.CASCADE,  null=True,
                                   blank=True)
    active = models.BooleanField(default=False)
    dirty =models.BooleanField(default=False)
    url = models.URLField(max_length=255, blank=True, null=True)
    auth_token = models.CharField(max_length=255, blank=True, null=True)
    last_request = models.TextField(blank=True, null=True)
    last_request_body = models.TextField(blank=True, null=True)
    last_response = models.JSONField(blank=True, null=True)
    last_result = models.TextField(blank=True, null=True)

