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
from users.forms import UserForm, LocGroupsForm
from users.models import User, LocGroup, ApplicatieSleutel

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
    def usergrouplist(applicatie_id=None):
        if applicatie_id:
            users = User.objects.filter(applicatie_id=applicatie_id, is_active=True).order_by('-is_staff', 'username')
        else:
            users = User.objects.filter(is_superuser=True, is_active=True).order_by('-is_staff', 'username')
        for user in users:
            try:
                usable_password = user.is_staff or (user.applicatie is not None and user.applicatie.applicatie_sleutel is not None and is_password_usable(user.applicatie.applicatie_sleutel.password))
            except:
                usable_password = False
            yield(
                {
                    'username': user.username,
                    'userid': user.id,
                    'is_staff': user.is_staff,
                    'usable_password': usable_password,
                    'form_id': f'"form_{user.id}"',
                    'groups': ', '.join(map(lambda g: g.name, user.locgroup.all())),
                }
            )

    def get(self, *args, **kwargs):

        try:
            next = args[0].GET.get('next', '/')
            client_id = parse.parse_qs(parse.urlparse(next).query)['client_id'][0]
            applicatie_id = Application.objects.get(client_id=client_id).id
            applicatie_naam = Application.objects.get(client_id=client_id).name
            message = f'Kies een van de gebruikers om in te loggen bij {applicatie_naam}.'
        except (KeyError, Application.DoesNotExist):
            applicatie_id = None
            message = 'Configuratie inconsistent'

        if next == '/':
            message = 'Kies een gebruiker om in te loggen voor het beheer van ETI'

        return render(
            self.request,
            'users/testuserlist.html',
            {
                'usergrouplist': self.usergrouplist(applicatie_id),
                'next': next,
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
            if user.applicatie and user.applicatie.applicatie_sleutel:
                encoded = user.applicatie.applicatie_sleutel.password
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
                       'user_list': User.objects.filter(applicatie__name=kwargs['applicatie']).all(),
                       'applicatie': kwargs['applicatie'],
                   })
    except User.DoesNotExist:
        return HttpResponseNotFound('User or applcation does not exist')

@login_required(login_url='accounts/login')
def new_user(request, *args, **kwargs):
    applicatie = Application.objects.get(name=kwargs['applicatie'])
    new_name = f'new_{applicatie.name}'
    try:
        user = User.objects.get(username=new_name)
    except User.DoesNotExist:
        user = User.objects.create(applicatie=applicatie)
        user.username = new_name
        user.is_staff = False
        user.is_active = True
        user.save()
    return HttpResponseRedirect(reverse('user-detail', args=(user.id,)))

@login_required(login_url='accounts/login')
def user_delete(request, *args, **kwargs):
    try:
        user = User.objects.get(id=kwargs['userid'])
        applicatie = user.applicatie.name
        user.delete()
        return HttpResponseRedirect(reverse('user-list', args=(applicatie,)))
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

        userform = UserForm(instance=user)

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


@login_required(login_url='accounts/login')
def edit_groups(request, *args, **kwargs):
    try:
        applicatie = Application.objects.get(name=kwargs['applicatie'])
    except (Application.DoesNotExist, KeyError):
        return HttpResponseNotFound('Applicatie does not exist')
    if request.method == 'GET':
        groupsform = LocGroupsForm(instance=applicatie)
        return render(request, 'users/edit_groups.html', {
            'applicatie': applicatie.name,
            'groupsform': groupsform
        })
    elif request.method == 'POST':
        groupsform = LocGroupsForm(request.POST, instance=applicatie)
        if groupsform.is_valid():
            groupsform.save()
            return HttpResponseRedirect(reverse('edit-groups', args=(applicatie.name,)))
    return None


class GroupView(PermissionRequiredMixin, View):
    permission_required = 'staff'
    def get(self, *args, **kwargs):
        return render(self.request, 'users/group.html')


class AppPasswordView(PermissionRequiredMixin, View):
    permission_required = 'staff'

    def get(self, *args, **kwargs):
        try:
            applicatie = Application.objects.get(name=kwargs['applicatie'])
        except (Application.DoesNotExist, KeyError):
            return HttpResponseNotFound('Applicatie does not exist')
        try:
            old_encoded_password = applicatie.applicatie_sleutel.password
        except ApplicatieSleutel.DoesNotExist:
            applicatie.applicatie_sleutel = ApplicatieSleutel()
            applicatie.applicatie_sleutel.save()
            applicatie.save()

        return render(self.request, 'users/set_app_password', {
            'applicatie': applicatie.name,
            'message': '',
        })

    def post(self, *args, **kwargs):
        try:
            password = self.request.POST.get('password')
            checkpassword = self.request.POST.get('checkpassword')
        except KeyError:
            return HttpResponseNotFound()
        applicatie = Application.objects.get(name=kwargs['applicatie'])
        if password != checkpassword:
             return render(self.request, 'users/set_app_password', {
                 'applicatie': applicatie.name,
                 'message': 'Wachtwoorden zijn niet gelijk',
             })
        else:
            applicatie.applicatie_sleutel.password = make_password(password)
            applicatie.applicatie_sleutel.save()
            return HttpResponseRedirect(reverse('iam-root'))