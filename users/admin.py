from django.contrib import admin
from .models import User, SyncPoint, LocGroup


class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email')
    search_fields = ('username', 'email')

admin.site.register(User, UserAdmin)

class LocGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'applicatie',)
    search_fields = ('name',)

admin.site.register(LocGroup, LocGroupAdmin)

class SyncPointAdmin(admin.ModelAdmin):
    list_display = ('applicatie', 'url', 'auth_token')

admin.site.register(SyncPoint, SyncPointAdmin)