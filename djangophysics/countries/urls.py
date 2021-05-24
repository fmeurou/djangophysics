"""
Country URLs
"""

from django.conf.urls import url, include
from rest_framework import routers

from .views import FlagView
from .viewsets import CountryViewset, CountrySubdivisionViewset

app_name = 'countries'

router = routers.DefaultRouter()
router.register(r'', CountryViewset, basename='countries')
router.register(r'(?P<alpha_2>\w+)/subdivisions',
                CountrySubdivisionViewset, basename='subdivisions')

urlpatterns = [

    url(r'^', include(router.urls)),
    url(r'^(?P<pk>[^/.]+)/flag/$', FlagView.as_view()),
]
