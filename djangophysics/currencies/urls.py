"""
URLs for currencies module
"""

from django.urls import re_path, include
from rest_framework import routers

from .viewsets import CurrencyViewset

app_name = 'currencies'

router = routers.DefaultRouter()
router.register(r'', CurrencyViewset, basename='currencies')

urlpatterns = [
    re_path(r'^', include(router.urls)),
]
