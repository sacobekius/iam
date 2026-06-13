from django import forms
from django.contrib.auth.models import Group

from oauth2_provider.models import Application
from users.models import User, Rol


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


class RolForm(forms.ModelForm):
    class Meta:
        model = Rol
        fields = ('name',)


RollenFormSet = forms.inlineformset_factory(Application, Rol, form=RolForm, extra=3, can_delete=True)


class UserForm(forms.ModelForm):

    locusername = forms.CharField(label='Gebruikersnaam', max_length=255, required=False)

    class Meta:
        model = User
        fields = ('locusername', 'personeelsnummer', 'email', 'rollen',)
        widgets = {
            'rollen': forms.CheckboxSelectMultiple({'class': 'user-group-checkbox'}),
        }
        help_texts = {
            'username': None,
            'groups': None,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance.pk and self.instance.application:
            self.fields['rollen'].queryset = Rol.objects.filter(
                application=self.instance.application
            )
        else:
            self.fields['rollen'].queryset = Rol.objects.none()

    def save(self, commit=True):
        self.instance.locusername = self.cleaned_data['locusername']
        return super(UserForm, self).save(commit)


class GroepForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ('name',)


class GroepMembersForm(forms.Form):
    gebruikers = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(is_active=True).order_by('application__name', 'username'),
        widget=forms.CheckboxSelectMultiple({'class': 'user-group-checkbox'}),
        required=False,
        label='Gebruikers',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['gebruikers'].label_from_instance = lambda u: (
            f'{u.locusername} ({u.application.name})' if u.application else u.username
        )