from django import forms

from oauth2_provider.models import Application
from users.models import User, LocGroup

class AddLocGroupForm(forms.ModelForm):
    class Meta:
        model = LocGroup
        fields = ('name',)

LocGroupsForm = forms.inlineformset_factory(Application, LocGroup, form=AddLocGroupForm, extra=1, can_delete=True)

class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('username', 'personeelsnummer', 'email', 'locgroup')
        widgets = {
            'locgroup': forms.CheckboxSelectMultiple({'class': 'user-group-checkbox'}),
        }
        help_texts = {
            'username': None,
            'groups': None,
        }