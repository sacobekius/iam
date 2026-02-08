from django import forms

from oauth2_provider.models import Application
from users.models import User, LocGroup


class ApplicationForm(forms.ModelForm):
    spurl = forms.URLField(label='SCIM url', max_length=255, required=False)
    spactive = forms.BooleanField(label='SCIM actief', required=False)
    spauth_token = forms.CharField(label='SCIM token', max_length=255, required=False)

    class Meta:
        model = Application
        fields = ('name',
                  'redirect_uris',
                  'post_logout_redirect_uris',
                  'client_type',
                  'authorization_grant_type',
                  'client_id',
                  'client_secret',
                  'spurl',
                  'spactive',
                  'spauth_token')


class LocGroupForm(forms.ModelForm):
    class Meta:
        model = LocGroup
        fields = ('name',)


LocGroupsForm = forms.inlineformset_factory(Application, LocGroup, form=LocGroupForm, extra=3, can_delete=True)


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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance.pk and self.instance.application:
            self.fields['locgroup'].queryset = LocGroup.objects.filter(
                application=self.instance.application
            )
        else:
            self.fields['locgroup'].queryset = LocGroup.objects.none()

    def save(self, commit=True):
        self.instance.locusername = self.cleaned_data['locusername']
        return super(UserForm, self).save(commit)