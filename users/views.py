import base64
import json
import secrets
import urllib.parse

import requests as http_requests
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin, AccessMixin
from django.db import transaction
from django.contrib.auth.hashers import check_password, is_password_usable, make_password
from django.http import HttpResponse, HttpResponseNotFound, HttpResponseRedirect, JsonResponse, \
    HttpResponseNotAllowed, HttpResponseServerError
from django.contrib.auth import logout, login
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, reverse
from django.views import View

from oauth2_provider.models import Application
from django.contrib.auth.models import Group
from django.shortcuts import get_object_or_404

from users.forms import UserForm, RollenFormSet, ApplicationForm, GroepForm, GroepMembersForm
from users.models import User, Rol, ApplicatieSleutel, SyncPoint

from users.scimcomm import *

from urllib import parse

@login_required(login_url='accounts/login')
def iam_root(request):
    applications = []
    for application in Application.objects.all():
        applications.append({'name': application.name})
    return render(request, 'users/root.html', {
        'applications': applications,
        'is_staff': request.user.is_staff,
    })


class LoginView(View):

    @staticmethod
    def usergrouplist(application_id=None):
        if application_id:
            users = User.objects.filter(application_id=application_id, is_active=True).order_by('-is_staff', 'username')
        else:
            users = User.objects.filter(is_superuser=True, is_active=True).order_by('-is_staff', 'username')
        for user in users:
            try:
                usable_password = user.is_staff or (user.application is not None and user.application.application_sleutel is not None and is_password_usable(user.application.application_sleutel.password))
            except:
                usable_password = False
            yield(
                {
                    'username': user.locusername,
                    'userid': user.id,
                    'is_staff': user.is_staff,
                    'usable_password': usable_password,
                    'form_id': f'"form_{user.id}"',
                    'groups': ', '.join(map(lambda g: g.name, user.rollen.all())),
                }
            )

    def get(self, *args, **kwargs):

        nexturl = args[0].GET.get('next', '/')
        try:
            client_id = parse.parse_qs(parse.urlparse(nexturl).query)['client_id'][0]
            application = Application.objects.get(client_id=client_id)
            application_id = application.id
            application_naam = application.name
            message = f'Kies een van de gebruikers om in te loggen bij {application_naam}. ({application.application_syncpoint.synchronisatie_status})'
        except (KeyError, Application.DoesNotExist):
            application_id = None
            message = 'Configuratie inconsistent'

        if nexturl == '/':
            message = 'Kies een gebruiker om in te loggen voor het beheer van ETI'

        return render(
            self.request,
            'users/testuserlist.html',
            {
                'usergrouplist': self.usergrouplist(application_id),
                'next': nexturl,
                'message': message,
            }
        )


    def post(self, *args, **kwargs):

        try:
            next = self.request.POST.get('next')
            userid = self.request.POST.get('userid')
            password = self.request.POST.get('password')
        except KeyError:
            return HttpResponseNotFound()

        try:
            user = User.objects.get(id=userid)
        except User.DoesNotExist:
            return HttpResponseNotFound()

        encoded = None
        try:
            if user.application and user.application.application_sleutel:
                encoded = user.application.application_sleutel.password
        except:
            pass
        if user.is_staff:
            encoded = user.password

        if encoded is None or check_password(password, encoded):
            login(self.request, user)
            return HttpResponseRedirect(next)
        else:
            return render(
                self.request,
                'users/testuserlist.html',
                {
                    'usergrouplist': self.usergrouplist(),
                    'next': next,
                    'message': 'Het wachtwoord hoort niet bij de gekozen gebruiker.'
                }
            )


@login_required(login_url='accounts/login')
def list_users(request, *args, **kwargs):
    try:
        return render(request,
                   'users/user_list.html',
                   {
                       'user_list': User.objects.filter(application__name=kwargs['application']).all(),
                       'application': kwargs['application'],
                   })
    except User.DoesNotExist:
        return HttpResponseNotFound('User or applcation does not exist')

@login_required(login_url='accounts/login')
def new_user(request, *args, **kwargs):
    application = Application.objects.get(name=kwargs['application'])
    new_name = f'new_{application.name}'
    try:
        user = User.getbylocusername(application.name, new_name)
    except User.DoesNotExist:
        user = User.objects.create(application=application, username=f'{application.name}_{new_name}')
        user.locusername = new_name
        user.is_staff = False
        user.is_active = True
        user.save()
    return HttpResponseRedirect(reverse('user-detail', args=(user.id,)))

@login_required(login_url='accounts/login')
def delete_user(request, *args, **kwargs):
    try:
        user = User.objects.get(id=kwargs['userid'])
        application = user.application.name
        user.delete()
        return HttpResponseRedirect(reverse('user-list', args=(application,)))
    except (User.DoesNotExist, KeyError):
        return HttpResponseNotFound('User does not exist')

class UserView(AccessMixin, View):
    login_url='accounts/login'
    def get_user(self, *args, **kwargs):
        try:
            return User.objects.get(id=kwargs['userid'])
        except KeyError:
            return HttpResponseNotFound('Missing userid')
        except User.DoesNotExist:
            return HttpResponseNotFound('User does not exist')

    def get(self, *args, **kwargs):

        user = self.get_user(*args, **kwargs)
        if type(user) is not User:
            return HttpResponseServerError('')

        userform = UserForm(instance=user, initial={'locusername': user.locusername})

        return render(self.request,
                      'users/user.html',
                      {
                          'userform': userform,
                      })

    def post(self, *args, **kwargs):

        user = self.get_user(*args, **kwargs)
        if type(user) is not User:
            return HttpResponseServerError('')

        userform = UserForm(self.request.POST, instance=user)

        if userform.is_valid():
            userform.save()
            return HttpResponseRedirect(reverse('user-detail', args=(user.id,)))
        else:
            return render(self.request,
                          'users/user.html',
                          {
                              'userform': userform,
                          })

def new_application(request, *args, **kwargs):
    if request.method == 'GET':
        if application := request.GET.get('application'):
            return edit_application(request, application=application, *args, **kwargs)
        else:
            return HttpResponseNotFound('Missing application parameter')
    else:
        return HttpResponseNotAllowed(['GET',])

@login_required(login_url='accounts/login')
def delete_application(request, *args, **kwargs):
    try:
        application = Application.objects.get(name=kwargs['application'])
        Rol.objects.filter(application=application).delete()
        User.objects.filter(application=application).delete()
        if application.application_syncpoint:
            application.application_syncpoint.delete()
        application.delete()
        return HttpResponseRedirect(reverse('iam-root'))
    except (Application.DoesNotExist, KeyError):
        return HttpResponseNotFound('Application does not exist')

@login_required(login_url='accounts/login')
def edit_application(request, *args, **kwargs):
    try:
        application = Application.objects.get(name=kwargs['application'])
    except (Application.DoesNotExist, KeyError):
        application = Application.objects.create(
            name=kwargs['application'],
            hash_client_secret=False,
            authorization_grant_type=Application.GRANT_OPENID_HYBRID,
            client_type=Application.CLIENT_CONFIDENTIAL,
            algorithm='RS256',
        )
    try:
        syncpoint = application.application_syncpoint
    except Application.application_syncpoint.RelatedObjectDoesNotExist:
        syncpoint = SyncPoint.objects.create(application=application, active=False)
        application.application_syncpoint = syncpoint
    if request.method == 'GET':
        applicationform = ApplicationForm(instance=application,
                                          initial={'spurl': application.application_syncpoint.url,
                                                   'spactive': application.application_syncpoint.active,
                                                   'spauth_token': application.application_syncpoint.auth_token
                                                   })
    elif request.method == 'POST':
        applicationform = ApplicationForm(request.POST, instance=application)
        if applicationform.is_valid():
            applicationform.save()
            syncpoint.url = applicationform.cleaned_data['spurl']
            syncpoint.active = applicationform.cleaned_data['spactive']
            syncpoint.auth_token = applicationform.cleaned_data['spauth_token']
            syncpoint.mark_dirty()
            syncpoint.update_count += 1
            syncpoint.save()
            to_sync = SCIMProcess(syncpoint)
            to_sync.process()
            return HttpResponseRedirect(reverse('edit-application', args=(application.name,)))
    else:
        return HttpResponseNotAllowed(['GET', 'POST'])
    return render(request, 'users/application.html', context= {
        'applicationform': applicationform,
    })

@login_required(login_url='accounts/login')
def edit_rollen(request, *args, **kwargs):
    try:
        application = Application.objects.get(name=kwargs['application'])
    except (Application.DoesNotExist, KeyError):
        return HttpResponseNotFound('Applicatie does not exist')
    if request.method == 'GET':
        groupsform = RollenFormSet(instance=application)
    elif request.method == 'POST':
        groupsform = RollenFormSet(request.POST, instance=application)
        if groupsform.is_valid():
            groupsform.save()
            return HttpResponseRedirect(reverse('edit-rollen', args=(application.name,)))
    else:
        return HttpResponseNotAllowed(['GET', 'POST'])
    return render(request, 'users/edit_rollen.html', {
        'application': application.name,
        'groupsform': groupsform
    })


@login_required(login_url='accounts/login')
def groepen_list(request):
    if request.method == 'POST':
        form = GroepForm(request.POST)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect(reverse('groepen-list'))
    else:
        form = GroepForm()
    return render(request, 'users/groepen.html', {
        'groepen': Group.objects.all().order_by('name'),
        'form': form,
    })


class GroepView(LoginRequiredMixin, View):
    login_url = 'accounts/login'

    def get(self, request, groupid):
        groep = get_object_or_404(Group, id=groupid)
        naam_form = GroepForm(instance=groep)
        members_form = GroepMembersForm(initial={'gebruikers': groep.user_set.all()})
        return render(request, 'users/groep.html', {
            'groep': groep,
            'naam_form': naam_form,
            'members_form': members_form,
        })

    def post(self, request, groupid):
        groep = get_object_or_404(Group, id=groupid)
        naam_form = GroepForm(request.POST, instance=groep)
        members_form = GroepMembersForm(request.POST)
        if naam_form.is_valid() and members_form.is_valid():
            naam_form.save()
            groep.user_set.set(members_form.cleaned_data['gebruikers'])
            return HttpResponseRedirect(reverse('groep-detail', args=(groupid,)))
        return render(request, 'users/groep.html', {
            'groep': groep,
            'naam_form': naam_form,
            'members_form': members_form,
        })


@login_required(login_url='accounts/login')
def delete_groep(request, groupid):
    groep = get_object_or_404(Group, id=groupid)
    groep.delete()
    return HttpResponseRedirect(reverse('groepen-list'))


def test_hybrid_login(request):
    state = secrets.token_urlsafe(16)
    nonce = secrets.token_urlsafe(16)
    request.session['hybrid_state'] = state
    request.session['hybrid_nonce'] = nonce
    params = {
        'response_type': 'code id_token',
        'client_id': settings.TEST_HYBRID_CLIENT_ID,
        'redirect_uri': request.build_absolute_uri('/test/hybrid/callback/'),
        'scope': 'openid profile User.Read',
        'state': state,
        'nonce': nonce,
    }
    return HttpResponseRedirect('/o/authorize/?' + urllib.parse.urlencode(params))


def test_hybrid_callback(request):
    error = request.GET.get('error')
    if error:
        return render(request, 'users/test_hybrid_attributes.html', {'error': error})
    return render(request, 'users/test_hybrid_callback.html')


def test_hybrid_process(request):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    if request.POST.get('state') != request.session.get('hybrid_state'):
        return render(request, 'users/test_hybrid_attributes.html', {'error': 'Invalid state'})

    code = request.POST.get('code')
    front_id_token = request.POST.get('id_token', '')

    front_id_token_claims = {}
    if front_id_token:
        try:
            payload = front_id_token.split('.')[1]
            payload += '=' * (-len(payload) % 4)
            front_id_token_claims = json.loads(base64.b64decode(payload))
        except Exception:
            pass

    token_response = http_requests.post(
        request.build_absolute_uri('/o/token/'),
        data={
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': request.build_absolute_uri('/test/hybrid/callback/'),
            'client_id': settings.TEST_HYBRID_CLIENT_ID,
            'client_secret': settings.TEST_HYBRID_CLIENT_SECRET,
        },
    )
    if not token_response.ok:
        try:
            err = token_response.json()
        except ValueError:
            return HttpResponse(token_response.text, status=token_response.status_code, content_type='text/html')
        return render(request, 'users/test_hybrid_attributes.html', {'error': err})

    tokens = token_response.json()

    back_id_token_claims = {}
    if 'id_token' in tokens:
        try:
            payload = tokens['id_token'].split('.')[1]
            payload += '=' * (-len(payload) % 4)
            back_id_token_claims = json.loads(base64.b64decode(payload))
        except Exception:
            pass

    userinfo = {}
    userinfo_error = None
    userinfo_response = http_requests.get(
        request.build_absolute_uri('/o/userinfo/'),
        headers={'Authorization': f'Bearer {tokens["access_token"]}'},
    )
    if userinfo_response.ok:
        userinfo = userinfo_response.json()
    else:
        try:
            userinfo_error = userinfo_response.json()
        except ValueError:
            return HttpResponse(userinfo_response.text, status=userinfo_response.status_code, content_type='text/html')

    return render(request, 'users/test_hybrid_attributes.html', {
        'granted_scopes': tokens.get('scope', '').split(),
        'front_id_token_claims': front_id_token_claims,
        'back_id_token_claims': back_id_token_claims,
        'userinfo': userinfo,
        'userinfo_error': userinfo_error,
    })


def test_authcode_login(request, application):
    try:
        app = Application.objects.get(name=application)
    except Application.DoesNotExist:
        return HttpResponseNotFound('Applicatie niet gevonden')

    redirect_uri = request.build_absolute_uri('/test/authcode/callback/')
    if redirect_uri not in app.redirect_uris:
        app.redirect_uris = (app.redirect_uris + '\n' + redirect_uri).strip()
        app.save()

    state = secrets.token_urlsafe(16)
    request.session['authcode_state'] = state
    request.session['authcode_client_id'] = app.client_id
    request.session['authcode_client_secret'] = app.client_secret
    request.session['authcode_application'] = application

    params = {
        'response_type': 'code',
        'client_id': app.client_id,
        'redirect_uri': redirect_uri,
        'scope': 'openid profile User.Read',
        'state': state,
    }
    return HttpResponseRedirect('/o/authorize/?' + urllib.parse.urlencode(params))


def test_authcode_callback(request):
    error = request.GET.get('error')
    if error:
        return render(request, 'users/test_attributes.html', {'error': error})

    if request.GET.get('state') != request.session.get('authcode_state'):
        return render(request, 'users/test_attributes.html', {'error': 'Invalid state parameter'})

    redirect_uri = request.build_absolute_uri('/test/authcode/callback/')
    token_response = http_requests.post(
        request.build_absolute_uri('/o/token/'),
        data={
            'grant_type': 'authorization_code',
            'code': request.GET.get('code'),
            'redirect_uri': redirect_uri,
            'client_id': request.session.get('authcode_client_id'),
            'client_secret': request.session.get('authcode_client_secret'),
        },
    )
    if not token_response.ok:
        try:
            err = token_response.json()
            return render(request, 'users/test_attributes.html', {'error': err})
        except ValueError:
            return HttpResponse(token_response.text, status=token_response.status_code, content_type='text/html')

    tokens = token_response.json()

    id_token_claims = {}
    if 'id_token' in tokens:
        try:
            payload = tokens['id_token'].split('.')[1]
            payload += '=' * (-len(payload) % 4)
            id_token_claims = json.loads(base64.b64decode(payload))
        except Exception:
            pass

    userinfo = {}
    userinfo_error = None
    userinfo_response = http_requests.get(
        request.build_absolute_uri('/o/userinfo/'),
        headers={'Authorization': f'Bearer {tokens["access_token"]}'},
    )
    if userinfo_response.ok:
        userinfo = userinfo_response.json()
    else:
        try:
            userinfo_error = userinfo_response.json()
        except ValueError:
            return HttpResponse(userinfo_response.text, status=userinfo_response.status_code, content_type='text/html')

    return render(request, 'users/test_attributes.html', {
        'application': request.session.get('authcode_application'),
        'granted_scopes': tokens.get('scope', '').split(),
        'id_token_claims': id_token_claims,
        'userinfo': userinfo,
        'userinfo_error': userinfo_error,
    })


class AppPasswordView(PermissionRequiredMixin, View):
    permission_required = 'staff'

    def get(self, *args, **kwargs):
        try:
            application = Application.objects.get(name=kwargs['application'])
        except (Application.DoesNotExist, KeyError):
            return HttpResponseNotFound('Applicatie does not exist')
        try:
            old_encoded_password = application.application_sleutel.password
        except ApplicatieSleutel.DoesNotExist:
            application.application_sleutel = ApplicatieSleutel()
            application.application_sleutel.save()
            application.save()

        return render(self.request, 'users/set_app_password', {
            'application': application.name,
            'message': '',
        })

    def post(self, *args, **kwargs):
        try:
            password = self.request.POST.get('password')
            checkpassword = self.request.POST.get('checkpassword')
        except KeyError:
            return HttpResponseNotFound()
        application = Application.objects.get(name=kwargs['application'])
        if password != checkpassword:
             return render(self.request, 'users/set_app_password', {
                 'application': application.name,
                 'message': 'Wachtwoorden zijn niet gelijk',
             })
        else:
            application.application_sleutel.password = make_password(password)
            application.application_sleutel.save()
            return HttpResponseRedirect(reverse('iam-root'))