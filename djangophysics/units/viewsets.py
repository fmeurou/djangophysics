"""
Units module APIs viewsets
"""

import logging

from django.db import models
from django.http import HttpResponseForbidden, HttpRequest
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie
from django_filters import rest_framework as filters
from django.conf import settings
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.status import HTTP_404_NOT_FOUND, HTTP_400_BAD_REQUEST
from rest_framework.views import APIView
from rest_framework.viewsets import ViewSet, ModelViewSet

from djangophysics.converters.models import ConverterLoadError
from djangophysics.converters.serializers import ConverterResultSerializer
from djangophysics.core.helpers import validate_language
from djangophysics.core.pagination import PageNumberPagination
from . import DIMENSIONS
from .settings import DOMAINS
from .exceptions import UnitConverterInitError, UnitSystemNotFound, \
    UnitNotFound, DimensionNotFound, UnitValueError
from .filters import CustomUnitFilter, CustomDimensionFilter
from .forms import CustomUnitForm, CustomDimensionForm
from .models import UnitSystem, UnitConverter, Dimension, CustomUnit, \
    CustomDimension
from .permissions import CustomUnitObjectPermission, \
    CustomDimensionObjectPermission
from .serializers import UnitSerializer, UnitSystemSerializer, \
    UnitConversionPayloadSerializer, DimensionSerializer, \
    DimensionWithUnitsSerializer, CustomUnitSerializer, \
    CustomDimensionSerializer

try:
    PHYSICS_DOMAINS = settings.PHYSICS_DOMAINS
except AttributeError:
    PHYSICS_DOMAINS = DOMAINS


class UnitSystemViewset(ViewSet):
    """
    View for currency
    """
    lookup_field = 'system_name'

    language_header = openapi.Parameter(
        'Accept-Language', openapi.IN_HEADER,
        description="language",
        type=openapi.TYPE_STRING)
    language = openapi.Parameter(
        'language', openapi.IN_QUERY,
        description="language",
        type=openapi.TYPE_STRING)
    key = openapi.Parameter(
        'user custom key', openapi.IN_QUERY,
        description="key",
        type=openapi.TYPE_STRING)

    unit_systems_response = openapi.Response(
        'List of unit systems',
        UnitSystemSerializer)
    unit_system_response = openapi.Response(
        'Dimensions and units in a system',
        UnitSystemSerializer)

    ordering = openapi.Parameter(
        'ordering', openapi.IN_QUERY,
        description="Sort on name Prefix with - for descending sort",
        type=openapi.TYPE_STRING)

    @method_decorator(cache_page(60 * 60 * 24))
    @method_decorator(vary_on_cookie)
    @swagger_auto_schema(
        manual_parameters=[language, language_header, ordering],
        responses={200: unit_systems_response})
    def list(self, request):
        """
        List UnitSystems
        """
        ordering = request.GET.get('ordering', 'system_name')
        descending = False
        if ordering and ordering[0] == '-':
            ordering = ordering[1:]
            descending = True
        if ordering not in ['system_name']:
            ordering = 'system_name'
        language = validate_language(request.GET.get('language',
                                                     request.LANGUAGE_CODE))
        us = UnitSystem(fmt_locale=language)
        us = [{'system_name': s} for s in sorted(us.available_systems(),
                                                 reverse=descending)]
        return Response(us, content_type="application/json")

    @method_decorator(cache_page(60 * 60 * 24))
    @method_decorator(vary_on_cookie)
    @swagger_auto_schema(manual_parameters=[language, language_header],
                         responses={200: unit_system_response})
    def retrieve(self, request, system_name):
        """
        Retrieve UnitSystem
        """
        language = validate_language(request.GET.get('language',
                                                     request.LANGUAGE_CODE))
        try:
            us = UnitSystem(system_name=system_name, fmt_locale=language)
            serializer = UnitSystemSerializer(us, context={'request': request})
            return Response(serializer.data, content_type="application/json")
        except UnitSystemNotFound as e:
            return Response("Unknown unit system: " + str(e),
                            status=HTTP_404_NOT_FOUND)

    @method_decorator(vary_on_cookie)
    @swagger_auto_schema(
        manual_parameters=[language, language_header, key, ordering],
        responses={200: DimensionSerializer})
    @action(methods=['GET'], detail=True,
            name='dimensions', url_path='dimensions')
    def dimensions(self, request, system_name):
        """
        List Dimensions of a UnitSystem
        """
        key = request.GET.get('key')
        language = validate_language(request.GET.get('language',
                                                     request.LANGUAGE_CODE))
        ordering = request.GET.get('ordering', 'name')
        descending = False
        if ordering and ordering[0] == '-':
            ordering = ordering[1:]
            descending = True
        if ordering not in ['code', 'name']:
            ordering = 'name'
        try:
            if request.user and request.user.is_authenticated:
                us = UnitSystem(
                    system_name=system_name,
                    user=request.user,
                    key=key,
                    fmt_locale=language)
            else:
                us = UnitSystem(
                    system_name=system_name,
                    fmt_locale=language)
            serializer = DimensionSerializer(
                sorted(us.available_dimensions().values(),
                       key=lambda x: getattr(x, ordering),
                       reverse=descending),
                many=True,
                context={'request': request})
            return Response(serializer.data, content_type="application/json")
        except UnitSystemNotFound as e:
            return Response("Unknown unit system: " + str(e),
                            status=HTTP_404_NOT_FOUND)


class UnitViewset(ViewSet):
    """
    View for currency
    """
    lookup_field = 'unit_name'
    language_header = openapi.Parameter(
        'Accept-Language', openapi.IN_HEADER,
        description="language",
        type=openapi.TYPE_STRING)
    language = openapi.Parameter(
        'language', openapi.IN_QUERY,
        description="language",
        type=openapi.TYPE_STRING)
    dimension = openapi.Parameter(
        'dimension', openapi.IN_QUERY,
        description="Unit dimension",
        type=openapi.TYPE_STRING)
    domain = openapi.Parameter(
        'domain', openapi.IN_QUERY,
        description="Unit domain (ghg, ...)",
        type=openapi.TYPE_STRING)
    key = openapi.Parameter(
        'key',
        openapi.IN_QUERY,
        description="key",
        type=openapi.TYPE_STRING)
    units_response = openapi.Response(
        'List of units in a system',
        UnitSerializer)
    unit_response = openapi.Response(
        'Detail of a unit',
        UnitSerializer)
    dimension_response = openapi.Response(
        'List of units per dimension',
        DimensionWithUnitsSerializer)
    ordering = openapi.Parameter(
        'ordering', openapi.IN_QUERY,
        description="Sort on fields name or code. "
                    "Prefix with - for descending sort",
        type=openapi.TYPE_STRING)

    @swagger_auto_schema(manual_parameters=[dimension, domain, key,
                                            ordering,
                                            language, language_header],
                         responses={200: units_response})
    def list(self, request: HttpRequest, system_name: str):
        """
        List Units, ordered, filtered by key or dimension,
        translated in language
        """
        language = validate_language(request.GET.get(
            'language', request.LANGUAGE_CODE))
        ordering = request.GET.get('ordering', 'name')
        descending = False
        if ordering and ordering[0] == '-':
            ordering = ordering[1:]
            descending = True
        if ordering not in ['code', 'name']:
            ordering = 'name'
        try:
            key = request.GET.get('key', None)
            user = request.user if \
                hasattr(request, 'user') and \
                request.user.is_authenticated else None
            us = UnitSystem(
                system_name=system_name,
                fmt_locale=language,
                user=user,
                key=key)
            units = []
            dimension_param = request.GET.get(key='dimension')
            domain_param = request.GET.get(key='domain')
            if dimension_param:
                try:
                    dimension = Dimension(unit_system=us,
                                          code=dimension_param)
                    units = dimension.units
                except (DimensionNotFound, UnitNotFound) as e:
                    return Response(f'Invalid dimension filter: {str(e)}',
                                    status=status.HTTP_400_BAD_REQUEST)
            else:
                available_units = us.available_unit_names()
                if available_units:
                    units = [us.unit(unit_name=unit_name)
                             for unit_name in available_units]
            if domain_param:
                units = [u for u in units if u.code in PHYSICS_DOMAINS.get(domain_param, [])]
            units = sorted(units, key=lambda x: getattr(x, ordering),
                           reverse=descending)
            serializer = UnitSerializer(
                units,
                many=True,
                context={'request': request})
            return Response(serializer.data)
        except UnitSystemNotFound as e:
            return Response(f'Invalid Unit System: {str(e)}',
                            status=status.HTTP_404_NOT_FOUND)

    @swagger_auto_schema(manual_parameters=[key, language, language_header],
                         responses={200: dimension_response})
    @action(['GET'], detail=False,
            name='units per dimension', url_path='per_dimension')
    def list_per_dimension(self, request: HttpRequest, system_name: str):
        """
        List Units grouped by dimension, filter on key, translated
        """
        language = validate_language(request.GET.get(
            'language',
            request.LANGUAGE_CODE)
        )
        try:
            key = request.GET.get('key', None)
            user = request.user if \
                hasattr(request, 'user') and \
                request.user.is_authenticated else None
            us = UnitSystem(
                system_name=system_name,
                fmt_locale=language,
                user=user,
                key=key)
            dimensions = us.dimensions_cache.values()
            serializer = DimensionWithUnitsSerializer(
                dimensions,
                many=True,
                context={'request': request})
            return Response(serializer.data)
        except UnitSystemNotFound as e:
            logging.warning(str(e))
            return Response('Invalid Unit System',
                            status=status.HTTP_404_NOT_FOUND)

    @method_decorator(vary_on_cookie)
    @swagger_auto_schema(manual_parameters=[key, language, language_header],
                         responses={200: unit_response})
    def retrieve(self, request: HttpRequest, system_name: str, unit_name: str):
        """
        Get unit information for unit in unit system
        """
        language = validate_language(request.GET.get('language',
                                                     request.LANGUAGE_CODE))
        try:
            key = request.GET.get('key', None)
            user = request.user if \
                hasattr(request, 'user') and \
                request.user.is_authenticated else None
            us = UnitSystem(
                system_name=system_name,
                fmt_locale=language,
                user=user,
                key=key)
            unit = us.unit(unit_name=unit_name)
            if not unit:
                return Response("Unknown unit", status=HTTP_404_NOT_FOUND)
            serializer = UnitSerializer(unit, context={'request': request})
            return Response(serializer.data, content_type="application/json")
        except (UnitSystemNotFound, UnitNotFound):
            return Response("Unknown unit", status=HTTP_404_NOT_FOUND)

    @swagger_auto_schema(
        manual_parameters=[language, language_header, ordering],
        responses={200: units_response})
    @action(methods=['GET'], detail=True,
            url_path='compatible', url_name='compatible_units')
    def compatible_units(self,
                         request: HttpRequest,
                         system_name: str,
                         unit_name: str):
        """
        List compatible Units
        """
        language = validate_language(request.GET.get(
            'language',
            request.LANGUAGE_CODE)
        )
        ordering = request.GET.get('ordering', 'name')
        descending = False
        if ordering and ordering[0] == '-':
            ordering = ordering[1:]
            descending = True
        if ordering not in ['code', 'name']:
            ordering = 'name'
        try:
            key = request.GET.get('key', None)
            user = request.user if \
                hasattr(request, 'user') and \
                request.user.is_authenticated else None
            us = UnitSystem(
                system_name=system_name,
                fmt_locale=language,
                user=user,
                key=key)
            unit = us.unit(unit_name=unit_name)
            compatible_units = sorted([us.unit(unit_name=cunit) for cunit in
                                       map(str, unit.unit.compatible_units())],
                                      key=lambda x: getattr(x, ordering),
                                      reverse=descending)
            serializer = UnitSerializer(
                compatible_units,
                many=True,
                context={'request': request})
            return Response(serializer.data, content_type="application/json")
        except (UnitSystemNotFound, UnitNotFound):
            return Response("Unknown unit", status=HTTP_404_NOT_FOUND)


class ConvertView(APIView):
    """
    Convert Units API
    """

    @swagger_auto_schema(request_body=UnitConversionPayloadSerializer,
                         responses={200: ConverterResultSerializer})
    @action(['POST'], detail=False, url_path='', url_name="convert")
    def post(self, request, *args, **kwargs):
        """
        Converts a list of amounts with currency
        and date to a reference currency
        :param request: HTTP request
        """
        cps = UnitConversionPayloadSerializer(data=request.data)
        if not cps.is_valid():
            return Response(cps.errors, status=HTTP_400_BAD_REQUEST,
                            content_type="application/json")
        cp = cps.create(cps.validated_data)
        user = None
        if request.user and request.user.is_authenticated:
            user = request.user
        key = request.POST.get('key', None)
        try:
            converter = UnitConverter.load(user=user, key=key, id=cp.batch_id)
        except ConverterLoadError:
            converter = UnitConverter(
                id=cp.batch_id,
                base_system=cp.base_system,
                base_unit=cp.base_unit,
                user=user,
                key=key
            )
        except UnitConverterInitError:
            return Response("Error initializing converter",
                            status=status.HTTP_400_BAD_REQUEST)
        if cp.data:
            errors = converter.add_data(data=cp.data)
            if errors:
                return Response(errors, status=HTTP_400_BAD_REQUEST)
        if cp.eob or not cp.batch_id:
            result = converter.convert()
            serializer = ConverterResultSerializer(result)
            return Response(serializer.data, content_type="application/json")
        else:
            return Response({'id': converter.id, 'status': converter.status},
                            content_type="application/json")


class CustomDimensionViewSet(ModelViewSet):
    """
    Custom Dimensions API
    """
    queryset = CustomDimension.objects.all()
    serializer_class = CustomDimensionSerializer
    filter_backends = (filters.DjangoFilterBackend,)
    filterset_class = CustomDimensionFilter
    pagination_class = PageNumberPagination
    permission_classes = [CustomDimensionObjectPermission,
                          permissions.IsAuthenticated]
    display_page_controls = True
    lookup_url_param = 'system_name'

    user = openapi.Parameter(
        'user',
        openapi.IN_QUERY,
        description="Filter on user rates",
        type=openapi.TYPE_BOOLEAN)
    key = openapi.Parameter(
        'key',
        openapi.IN_QUERY,
        description="Filter on user defined category",
        type=openapi.TYPE_STRING)
    unit_system = openapi.Parameter(
        'unit_system',
        openapi.IN_QUERY,
        description="Filter on unit system",
        type=openapi.TYPE_STRING)
    code = openapi.Parameter(
        'code',
        openapi.IN_QUERY,
        description="Filter on unit code",
        type=openapi.TYPE_STRING)
    name = openapi.Parameter(
        'name',
        openapi.IN_QUERY,
        description="Filter on unit name",
        type=openapi.TYPE_STRING)
    relation = openapi.Parameter(
        'relation',
        openapi.IN_QUERY,
        description="Filter on relation to base units",
        type=openapi.TYPE_STRING)
    ordering = openapi.Parameter(
        'ordering',
        openapi.IN_QUERY,
        description="Sort on code, name, relation, symbol, alias. "
                    "Prefix with - for descending sort",
        type=openapi.TYPE_STRING)

    def get_queryset(self):
        """
        Filter units based on authenticated user
        """
        qs = super().get_queryset()
        system_name = self.kwargs.get(self.lookup_url_param, 'SI')
        no_user_filter = models.Q(user__isnull=True)
        if self.request.user and self.request.user.is_authenticated:
            key = self.request.GET.get('key')
            if key:
                key_filter = models.Q(key=self.request.GET.get('key'))
                user_filter = models.Q(user=self.request.user) & key_filter
            else:
                user_filter = models.Q(user=self.request.user)
            qs = qs.filter(user_filter | no_user_filter)
        else:
            qs = qs.filter(no_user_filter)
        qs = qs.filter(unit_system__iexact=system_name.lower())
        return qs

    @swagger_auto_schema(manual_parameters=[
        user, key, unit_system, code, name, relation, ordering],
        responses={200: CustomDimensionSerializer})
    def list(self, request, *args, **kwargs):
        """
        List custom dimensions
        """
        return super().list(request, *args, **kwargs)

    def create(self, request: HttpRequest, system_name: str, *args, **kwargs):
        """
        Create CustomDimension
        """
        cd_form = CustomDimensionForm(request.data)
        if cd_form.is_valid():
            cd = cd_form.save(commit=False)
            try:
                UnitSystem(
                    system_name=system_name,
                    user=request.user,
                    key=cd.key)
            except UnitSystemNotFound:
                return Response("Invalid unit system",
                                status=status.HTTP_400_BAD_REQUEST)
            if request.user and request.user.is_authenticated:
                if CustomDimension.objects.filter(
                        code=cd.code,
                        user=request.user,
                        key=cd.key).exists():
                    return Response("Custom unit already exists",
                                    status=status.HTTP_409_CONFLICT)
                cd.user = request.user
                cd.unit_system = system_name
                try:
                    cd.save()
                except (UnitValueError,
                        ValueError,
                        DimensionDimensionError) as e:
                    return Response(str(e),
                                    status=status.HTTP_400_BAD_REQUEST)
                serializer = CustomDimensionSerializer(cd)
                return Response(serializer.data,
                                status=status.HTTP_201_CREATED)
            else:
                return HttpResponseForbidden()
        else:
            return Response(cd_form.errors,
                            status=status.HTTP_400_BAD_REQUEST,
                            content_type="application/json")


class CustomUnitViewSet(ModelViewSet):
    """
    Custom Units API
    """
    queryset = CustomUnit.objects.all()
    serializer_class = CustomUnitSerializer
    filter_backends = (filters.DjangoFilterBackend,)
    filterset_class = CustomUnitFilter
    pagination_class = PageNumberPagination
    permission_classes = [CustomUnitObjectPermission,
                          permissions.IsAuthenticated]
    display_page_controls = True
    lookup_url_param = 'system_name'

    user = openapi.Parameter(
        'user',
        openapi.IN_QUERY,
        description="Filter on user rates",
        type=openapi.TYPE_BOOLEAN)
    key = openapi.Parameter(
        'key',
        openapi.IN_QUERY,
        description="Filter on user defined category",
        type=openapi.TYPE_STRING)
    unit_system = openapi.Parameter(
        'unit_system',
        openapi.IN_QUERY,
        description="Filter on unit system",
        type=openapi.TYPE_STRING)
    code = openapi.Parameter(
        'code',
        openapi.IN_QUERY,
        description="Filter on unit code",
        type=openapi.TYPE_STRING)
    name = openapi.Parameter(
        'name',
        openapi.IN_QUERY,
        description="Filter on unit name",
        type=openapi.TYPE_STRING)
    relation = openapi.Parameter(
        'relation',
        openapi.IN_QUERY,
        description="Filter on relation to base units",
        type=openapi.TYPE_STRING)
    symbol = openapi.Parameter(
        'symbol',
        openapi.IN_QUERY,
        description="Filter on unit symbol",
        type=openapi.TYPE_STRING)
    alias = openapi.Parameter(
        'alias',
        openapi.IN_QUERY,
        description="Filter on unit alias",
        type=openapi.TYPE_STRING)
    ordering = openapi.Parameter(
        'ordering',
        openapi.IN_QUERY,
        description="Sort on code, name, relation, symbol, alias. "
                    "Prefix with - for descending sort",
        type=openapi.TYPE_STRING)

    def get_queryset(self):
        """
        Filter units based on authenticated user
        """
        qs = super().get_queryset()
        system_name = self.kwargs.get(self.lookup_url_param, 'SI')
        no_user_filter = models.Q(user__isnull=True)
        if self.request.user and self.request.user.is_authenticated:
            key = self.request.GET.get('key')
            if key:
                key_filter = models.Q(key=self.request.GET.get('key'))
                user_filter = models.Q(user=self.request.user) & key_filter
            else:
                user_filter = models.Q(user=self.request.user)
            qs = qs.filter(user_filter | no_user_filter)
        else:
            qs = qs.filter(models.Q(user__isnull=True))
        qs = qs.filter(unit_system__iexact=system_name.lower())
        return qs

    @swagger_auto_schema(manual_parameters=[
        user, key, unit_system, code, name, relation, symbol, alias, ordering],
        responses={200: CustomUnitSerializer})
    def list(self, request, *args, **kwargs):
        """
        List units
        """
        return super().list(request, *args, **kwargs)

    def create(self, request: HttpRequest, system_name: str, *args, **kwargs):
        """
        Create CustomUnit
        """
        cu_form = CustomUnitForm(request.data)
        if cu_form.is_valid():
            dim_name = request.data.get('dimension')
            cu = cu_form.save(commit=False)
            try:
                UnitSystem(
                    system_name=system_name,
                    user=request.user,
                    key=cu.key)
            except UnitSystemNotFound:
                return Response("Invalid unit system",
                                status=status.HTTP_400_BAD_REQUEST)
            if request.user and request.user.is_authenticated:
                if CustomUnit.objects.filter(
                        code=cu.code,
                        user=request.user,
                        key=cu.key).exists():
                    return Response("Custom unit already exists",
                                    status=status.HTTP_409_CONFLICT)
                cu.user = request.user
                cu.unit_system = system_name
                try:
                    cu.save()
                except (UnitValueError, ValueError) as e:
                    return Response(str(e),
                                    status=status.HTTP_400_BAD_REQUEST)
                us = UnitSystem(
                    system_name=system_name,
                    user=request.user,
                    key=cu.key
                )
                if dim_name:
                    if dim_name in us.available_dimension_names():
                        try:
                            dim = Dimension(unit_system=us, code=dim_name)
                            if cu.code not in [u.code for u in dim.units]:
                                return Response(
                                    "Incoherent unit and dimension",
                                    status=status.HTTP_400_BAD_REQUEST
                                )
                        except DimensionNotFound:
                            cu.delete()
                            return Response(
                                "Invalid dimension",
                                status=status.HTTP_400_BAD_REQUEST
                            )
                    else:
                        unit = us.unit(cu.code)
                        CustomDimension.objects.create(
                            unit_system=system_name,
                            user=request.user,
                            key=cu.key,
                            name=dim_name,
                            code=dim_name,
                            relation=str(unit.dimensionality)
                        )
                serializer = CustomUnitSerializer(cu)
                return Response(serializer.data,
                                status=status.HTTP_201_CREATED)
            else:
                return HttpResponseForbidden()
        else:
            return Response(cu_form.errors,
                            status=status.HTTP_400_BAD_REQUEST,
                            content_type="application/json")