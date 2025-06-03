from django import forms
from django.contrib.auth.models import Group

from users.models import User

class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('username', 'email', 'groups')
        widgets = {
            'groups': forms.CheckboxSelectMultiple,
        }
        help_texts = {
            'username': None,
            'groups': 'Selecteer meerdere groepen met Ctrl op MS-Windows en Cmd op Mac OS'
        }