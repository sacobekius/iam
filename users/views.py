from django.http import HttpResponseNotFound, HttpResponseRedirect, JsonResponse
from django.contrib.auth import logout, login
from django.shortcuts import render, reverse
from django.views import View

from users.forms import UserForm
from users.models import User

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
                    'groups': ', '.join(map(lambda g : g.name, user.groups.all())),
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

def list_users(request):
    return render(request,
                   'users/user_list.html',
                   {
                       'user_list': User.objects.all(),
                   })

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
            return user

        userform = UserForm(instance=user)

        return render(self.request,
                      'users/user.html',
                      {
                          'userform': userform,
                      })

    def post(self, *args, **kwargs):

        user = self.get_user(*args, **kwargs)
        if type(user) is not User:
            return user

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


def list_groups(request):
    pass

class GroupView(View):

    def get(self, *args, **kwargs):

        return render(self.request, 'users/group.html')