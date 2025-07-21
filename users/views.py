from django.db import transaction
from django.http import HttpResponseNotFound, HttpResponseRedirect, JsonResponse, HttpResponseNotAllowed, \
    HttpResponseServerError
from django.contrib.auth import logout, login
from django.shortcuts import render, reverse
from django.views import View

from oauth2_provider.models import Application
from users.forms import UserForm, LocGroupsForm
from users.models import User, LocGroup

from users.scimcomm import *

def iam_root(request):
    applications = []
    for application in Application.objects.all():
        applications.append({'name': application.name})
    return render(request, 'users/root.html', { 'applications': applications })


class LoginView(View):

    def get(self, *args, **kwargs):

        next = args[0].GET.get('next', '/')

        usergrouplist = []
        users = User.objects.filter(is_active=True).filter(is_staff=False).order_by('username')

        for user in users:
            usergrouplist.append(
                {
                    'username': user.username,
                    'userid': user.id,
                    'form_id': f'"form_{user.id}"',
                    'groups': ', '.join(map(lambda g : g.name, user.locgroup.all())),
                }
            )

        return render(
            self.request,
            'users/testuserlist.html',
            {
                'usergrouplist': usergrouplist,
                'next': next,
            }
        )


    def post(self, *args, **kwargs):

        try:
            next = self.request.POST.get('next')
            userid = self.request.POST.get('userid')
        except KeyError:
            return HttpResponseNotFound()

        try:
            user = User.objects.get(id=userid)
        except User.DoesNotExist:
            return HttpResponseNotFound()

        login(self.request, user)

        return HttpResponseRedirect(next)

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

def new_user(request, *args, **kwargs):
    applicatie = Application.objects.get(name=kwargs['applicatie'])
    user = User.objects.create(applicatie=applicatie)
    user.username = f'new_{applicatie.name}'
    user.is_staff = False
    user.is_active = True
    user.save()
    return HttpResponseRedirect(reverse('user-detail', args=(user.id,)))

def user_delete(request, *args, **kwargs):
    try:
        user = User.objects.get(id=kwargs['userid'])
        applicatie = user.applicatie.name
        user.delete()
        return HttpResponseRedirect(reverse('user-list', args=(applicatie,)))
    except (User.DoesNotExist, KeyError):
        return HttpResponseNotFound('User does not exist')

class UserView(View):

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


class GroupView(View):

    def get(self, *args, **kwargs):

        return render(self.request, 'users/group.html')