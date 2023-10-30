"""
Country URLs
"""

from django.urls import re_path, include
from rest_framework import routers

from .views import FlagView
from .viewsets import CountryViewset, CountrySubdivisionViewset

app_name = 'countries'

router = routers.DefaultRouter()
router.register(r'', CountryViewset, basename='countries')
router.register(r'(?P<alpha_2>\w+)/subdivisions',
                CountrySubdivisionViewset, basename='subdivisions')

urlpatterns = [

    re_path(r'^', include(router.urls)),
    re_path(r'^(?P<pk>[^/.]+)/flag/$', FlagView.as_view(), name='flag'),
]
