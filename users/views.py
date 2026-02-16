from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.mixins import PermissionRequiredMixin, AccessMixin
from django.db import transaction
from django.contrib.auth.hashers import check_password, is_password_usable, make_password
from django.http import HttpResponseNotFound, HttpResponseRedirect, JsonResponse, HttpResponseNotAllowed, \
    HttpResponseServerError
from django.contrib.auth import logout, login
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, reverse
from django.views import View

from oauth2_provider.models import Application
from users.forms import UserForm, LocGroupsForm, ApplicationForm
from users.models import User, LocGroup, ApplicatieSleutel, SyncPoint

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
                    'groups': ', '.join(map(lambda g: g.name, user.locgroup.all())),
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
def edit_groups(request, *args, **kwargs):
    try:
        application = Application.objects.get(name=kwargs['application'])
    except (Application.DoesNotExist, KeyError):
        return HttpResponseNotFound('Applicatie does not exist')
    if request.method == 'GET':
        groupsform = LocGroupsForm(instance=application)
    elif request.method == 'POST':
        groupsform = LocGroupsForm(request.POST, instance=application)
        if groupsform.is_valid():
            groupsform.save()
            return HttpResponseRedirect(reverse('edit-groups', args=(application.name,)))
    else:
        return HttpResponseNotAllowed(['GET', 'POST'])
    return render(request, 'users/edit_groups.html', {
        'application': application.name,
        'groupsform': groupsform
    })


class GroupView(PermissionRequiredMixin, View):
    permission_required = 'staff'
    def get(self, *args, **kwargs):
        return render(self.request, 'users/group.html')


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