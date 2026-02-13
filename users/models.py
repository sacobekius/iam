from django.db import models
from django.contrib.auth.models import AbstractUser, Group
from oauth2_provider.models import Application

class LocGroup(models.Model):
    application = models.ForeignKey("oauth2_provider.Application",
                                   related_name='application_groups',
                                   on_delete=models.CASCADE,
                                   null=True,
                                   blank=True)
    name = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class User(AbstractUser):
    application = models.ForeignKey("oauth2_provider.Application", related_name='application_users',
                                   on_delete=models.CASCADE, null=True, blank=True)
    personeelsnummer = models.CharField(max_length=6, null=True, blank=True)
    locgroup = models.ManyToManyField(LocGroup, related_name='user_set', verbose_name='Groepen', blank=True)

    class Meta:
        ordering = ['username']

    @property
    def locusername(self):
        if self.application:
            apnmlen = len(self.application.name)
            if self.username[:apnmlen] != self.application.name:
                self.username = self.application.name + "_" + self.username
                try:
                    User.objects.get(username=self.username).delete()
                except User.DoesNotExist:
                    pass
                self.save()
            return self.username[apnmlen+1:]
        else:
            return self.username

    @locusername.setter
    def locusername(self, value):
        if self.application:
            self.username = self.application.name + '_' + value

    @classmethod
    def getbylocusername(cls, application_name, locusername):
        return User.objects.get(username=application_name + "_" + locusername)

class SyncPoint(models.Model):
    application = models.OneToOneField("oauth2_provider.Application", related_name='application_syncpoint',
                                      on_delete=models.CASCADE,  null=True, blank=True)
    active = models.BooleanField(default=False)
    dirty = models.BooleanField(default=False)
    busy = models.BooleanField(default=False)
    hit_while_busy = models.BooleanField(default=False)
    url = models.URLField(max_length=255, blank=True, null=True)
    auth_token = models.CharField(max_length=255, blank=True, null=True)
    last_request = models.TextField(blank=True, null=True)
    last_request_body = models.TextField(blank=True, null=True)
    last_response = models.JSONField(blank=True, null=True)
    last_result = models.TextField(blank=True, null=True)
    onverwachte_fout = models.TextField(max_length=255, blank=True, null=True)

    def synchronisatie_status(self):
        if self.last_request:
            return f'Synchronisatie stagneert: {self.last_result}'
        else:
            return 'Synchronisatie succesvol'

class ApplicatieSleutel(models.Model):
    application = models.OneToOneField("oauth2_provider.Application", related_name='application_sleutel',
                                      on_delete=models.CASCADE, null=True, blank=True)
    password = models.CharField(max_length=128, blank=True, null=True)