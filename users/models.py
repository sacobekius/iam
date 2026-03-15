from django.dispatch import receiver
from django.db.models.signals import pre_save, pre_delete, m2m_changed, post_save, post_delete

from django.db import models
from django.contrib.auth.models import AbstractUser, Group
from oauth2_provider.models import Application

import django.utils.timezone as timezone

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
    last_updated = models.DateTimeField(default=timezone.now)
    last_sync = models.DateTimeField(default=timezone.now)
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

    def mark_dirty(self):
        if self.active:
            self.last_updated = timezone.now()
            self.save()

    @property
    def synchronisatie_status(self):
        if self.onverwachte_fout:
            return f'{self.onverwachte_fout}'
        elif self.last_request:
            return f'{self.last_request} --> {self.last_result} {self.last_response}'
        else:
            if self.active:
                return f'Laatste update: {self.last_updated.astimezone().strftime("%d-%m-%Y, %H:%M:%S")}, Laatste synchronisatie: {self.last_sync.astimezone().strftime("%d-%m-%Y, %H:%M:%S")} was succesvol'
            else:
                return 'Synchronisatie is uitgeschakeld'


class ApplicatieSleutel(models.Model):
    application = models.OneToOneField("oauth2_provider.Application", related_name='application_sleutel',
                                      on_delete=models.CASCADE, null=True, blank=True)
    password = models.CharField(max_length=128, blank=True, null=True)


@receiver(m2m_changed, sender=User.locgroup.through)
def set_dirty_after_group_change(sender, instance, **kwargs):
    if 'action' in kwargs.keys() and kwargs['action'] in ['post_add', 'post_remove']:
        if type(instance) == User and instance.application and hasattr(instance.application, 'application_syncpoint'):
            instance.application.application_syncpoint.mark_dirty()

@receiver(post_save, sender=User)
@receiver(post_delete, sender=User)
def user_post_handler(sender, instance, **kwargs):
    if 'action' in kwargs.keys() and kwargs['action'] in ['pre_add', 'pre_remove']:
        return
    if type(instance) == User and instance.application and hasattr(instance.application, 'application_syncpoint'):
        instance.application.application_syncpoint.mark_dirty()

@receiver(post_save, sender=LocGroup)
@receiver(post_delete, sender=LocGroup)
def group_handler(sender, instance, **kwargs):
    relevant_syncpoints = []
    try:
        for user in instance.user_set.all():
            try:
                if user.application:
                    if user.application.application_syncpoint:
                        if user.application.application_syncpoint not in relevant_syncpoints:
                            relevant_syncpoints.append(user.application.application_syncpoint)
            except Application.application_syncpoint.RelatedObjectDoesNotExist:
                pass
    except ValueError:
        pass
    for syncpoint in relevant_syncpoints:
        syncpoint.mark_dirty()