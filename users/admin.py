from django.contrib import admin
from .models import User, SyncPoint, Rol, ApplicatieSleutel


class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email')
    search_fields = ('username', 'email')

admin.site.register(User, UserAdmin)

class RolAdmin(admin.ModelAdmin):
    list_display = ('name', 'application',)
    search_fields = ('name',)

admin.site.register(Rol, RolAdmin)

class SyncPointAdmin(admin.ModelAdmin):
    list_display = ('application', 'url', 'auth_token',)

admin.site.register(SyncPoint, SyncPointAdmin)

class ApplicatieSleutelAdmin(admin.ModelAdmin):
    list_display = ('application',)

admin.site.register(ApplicatieSleutel, ApplicatieSleutelAdmin)