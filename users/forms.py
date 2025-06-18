from django import forms
from django.contrib.auth.models import Group

from users.models import User
from django.contrib.auth.models import Group

GroupsForm = forms.modelformset_factory(Group, fields=('name',), extra=1, can_delete=True)

class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('username', 'personeelsnummer', 'email', 'groups')
        widgets = {
            'groups': forms.CheckboxSelectMultiple({'class': 'user-group-checkbox'}),
        }
        help_texts = {
            'username': None,
            'groups': None,
        }