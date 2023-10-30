"""
Units module URLs
"""

from django.urls import path, re_path, include
from rest_framework import routers

from .viewsets import UnitSystemViewset, UnitViewset, \
    ConvertView, CustomUnitViewSet, CustomDimensionViewSet
from djangophysics.calculations.viewsets import ValidateViewSet, CalculationView

app_name = 'units'

router = routers.DefaultRouter()
router.register(r'', UnitSystemViewset, basename='unit_systems')
router.register(r'(?P<system_name>\w+)/units/custom',
                CustomUnitViewSet, basename='custom_units')
router.register(r'(?P<system_name>\w+)/dimensions/custom',
                CustomDimensionViewSet, basename='custom_dimensions')
router.register(r'(?P<system_name>\w+)/units',
                UnitViewset, basename='units')
router.register(r'(?P<system_name>\w+)/custom',
                CustomUnitViewSet, basename='custom')


urlpatterns = [
    path('convert/', ConvertView.as_view()),
    path('<str:unit_system>/formulas/validate/', ValidateViewSet.as_view(), name='formula_validation'),
    path('<str:unit_system>/formulas/calculate/', CalculationView.as_view(), name='formula_calculation'),
    re_path(r'^', include(router.urls)),
]
