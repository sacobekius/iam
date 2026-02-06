from django import forms

from oauth2_provider.models import Application
from users.models import User, LocGroup


class AddLocGroupForm(forms.ModelForm):
    class Meta:
        model = LocGroup
        fields = ('name',)


LocGroupsForm = forms.inlineformset_factory(Application, LocGroup, form=AddLocGroupForm, extra=1, can_delete=True)


class UserForm(forms.ModelForm):

    locusername = forms.CharField(label='Gebruikersnaam', max_length=255, required=False)

    class Meta:
        model = User
        fields = ('locusername', 'personeelsnummer', 'email', 'locgroup',)
        widgets = {
            'locgroup': forms.CheckboxSelectMultiple({'class': 'user-group-checkbox'}),
        }
        help_texts = {
            'username': None,
            'groups': None,
        }

    def save(self, commit=True):
        self.instance.locusername = self.cleaned_data['locusername']
        return super(UserForm, self).save(commit)