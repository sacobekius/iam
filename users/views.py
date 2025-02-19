from django.http import HttpResponseNotFound, HttpResponseRedirect
from django.contrib.auth import logout, login
from django.shortcuts import render, reverse
from django.views import View

from users.models import User

class LoginView(View):

    def get(self, *args, **kwargs):

        if 'next' in args[0].GET.keys():
            next = args[0].GET['next']
        else:
            next = '/'

        usergrouplist = []
        users = User.objects.filter(is_active=True).filter(is_staff=False).order_by('username')

        for user in users:
            usergrouplist.append(
                {
                    'username': user.username,
                    'userid': user.id,
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
