"""
URL configuration for IAM project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from oauth2_provider import urls as oauth2_urls
from oauth2_provider.views import ConnectDiscoveryInfoView, RPInitiatedLogoutView

from users.views import LoginView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('o/', include(oauth2_urls)),
    # fix
    path("o/authorize/v2.0/.well-known/openid-configuration/", ConnectDiscoveryInfoView.as_view(),
         name="oidc-connect-discovery-info"),
    path("o/authorize/.well-known/openid-configuration/", ConnectDiscoveryInfoView.as_view(),
         name="oidc-connect-discovery-info"),

    path("o/authorize/oauth2/v2.0/logout/", RPInitiatedLogoutView.as_view(), name="rp-initiated-logout"),
    path('testusers/login/', LoginView.as_view(), name="testlogin"),
]
