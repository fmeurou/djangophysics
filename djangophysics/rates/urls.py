"""
Rates module URLs
"""

from django.urls import path, re_path, include
from rest_framework import routers

from .viewsets import RateViewSet, ConvertView

app_name = 'rates'

router = routers.DefaultRouter()
router.register(r'', RateViewSet, basename='rates')

urlpatterns = [
    path('convert/', ConvertView.as_view(), name='convert'),
    re_path(r'^', include(router.urls)),
]
