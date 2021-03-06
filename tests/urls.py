"""GeoCurrencies URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.0/topics/http/urls/
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
import os

from django.urls import re_path, include
from django.contrib import admin
from django.urls import path
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions

import djangophysics
from djangophysics import urls as physics_urls
from djangophysics.graphql import urls as graphql_urls

environment = os.environ.get('PHYSICS_ENV', 'dev')
contact_email = os.environ.get('PHYSICS_CONTACT', 'fm@peabytes.me')
api_url = os.environ.get('PHYSICS_URL', 'https://dev.geopysics.io/')

schema_view = get_schema_view(
    openapi.Info(
        title=f"Django Physics {environment} API",
        default_version='v1',
        description="APIs for Django Physics v" +
                    '.'.join(map(str, djangophysics.__version__[:3])),
        terms_of_service="/tos/",
        contact=openapi.Contact(email=contact_email),
        license=openapi.License(name="MIT License"),
    ),
    url=api_url,
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path('admin/', admin.site.urls),
    re_path(r'^swagger(?P<format>\.json|\.yaml)$',
        schema_view.without_ui(cache_timeout=0),
        name='schema-json'),
    re_path(r'^swagger/$', schema_view.with_ui('swagger', cache_timeout=0),
        name='schema-swagger-ui'),
    re_path(r'^redoc/$', schema_view.with_ui('redoc', cache_timeout=0),
        name='schema-redoc'),
    path('', include('django.contrib.auth.urls')),
    path('graphql', include(graphql_urls)),
    path('', include(physics_urls)),
]
