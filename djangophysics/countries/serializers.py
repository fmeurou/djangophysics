"""
Serializers for country classes
"""
import importlib
import gettext

import pycountry
from drf_yasg.utils import swagger_serializer_method
from djangophysics.core.helpers import validate_language
from pycountry import countries, subdivisions
from rest_framework import serializers

from .models import Country, CountrySubdivision


currency_serializer_module = importlib.import_module(
    'djangophysics.currencies.serializers')
currency_serializer_class = getattr(currency_serializer_module,
                                    'CurrencySerializer')


class CountrySerializer(serializers.Serializer):
    """
    Serializer for Country
    """
    name = serializers.CharField(
        label="ISO 3166 Country name",
        read_only=True)
    numeric = serializers.IntegerField(
        label="ISO numeric value",
        read_only=True)
    alpha_2 = serializers.CharField(
        label="ISO alpha-2 representation")
    alpha_3 = serializers.CharField(
        label="ISO alpha-3 representation",
        read_only=True)
    translated_name = serializers.SerializerMethodField(
        label="Translated country name")

    @staticmethod
    def validate_alpha2(alpha_2):
        """
        Validate that alpha 2 code is valid
        :param alpha_2: alpha 2 code from ISO3166
        """
        if countries.get(alpha_2=alpha_2):
            return alpha_2
        else:
            raise serializers.ValidationError('Invalid country alpha_2')

    def create(self, validated_data) -> Country:
        """
        Create a Country object
        :param validated_data: cleaned data
        """
        return Country(validated_data.get('alpha_2'))

    def update(self, instance, validated_data) -> Country:
        """
        Update a Country object
        :param instance: Contry object
        :param validated_data: cleaned data
        """
        country = Country(validated_data.get('alpha_2'))
        self.instance = country
        return self.instance

    @swagger_serializer_method(serializer_or_field=serializers.CharField)
    def get_translated_name(self, obj: Country) -> str:
        """
        Translate country name
        :param obj: Country
        :return: translated name
        """
        request = self.context.get('request', None)
        if request:
            try:
                language = validate_language(
                    request.GET.get('language',
                                    request.LANGUAGE_CODE))
                translation = gettext.translation(
                    'iso3166', pycountry.LOCALES_DIR,
                    languages=[language])
                translation.install()
                return translation.gettext(obj.name)
            except FileNotFoundError:
                return obj.name
        else:
            return obj.name


class CountryDetailSerializer(serializers.Serializer):
    """
    Detailed Serializer for Country
    """
    name = serializers.CharField(
        label="ISO-3306 Country name",
        read_only=True)
    numeric = serializers.IntegerField(
        label="ISO-3306 numeric value",
        read_only=True)
    alpha_2 = serializers.CharField(
        label="ISO alpha-2 representation",
        read_only=True)
    alpha_3 = serializers.CharField(
        label="ISO alpha-3 representation",
        read_only=True)
    region = serializers.SerializerMethodField(
        label="Geographic region of the country")
    subregion = serializers.SerializerMethodField(
        label="Geographic subregion of the country")
    tld = serializers.SerializerMethodField(
        label="Top Domain Level of the country")
    capital = serializers.SerializerMethodField(
        label="Name of the capital city")
    unit_system = serializers.SerializerMethodField(
        label="Main unit system for this country")
    translated_name = serializers.SerializerMethodField(
        label="Country translated name")
    currencies = currency_serializer_class(many=True,
        label="Currencies for this country")

    @swagger_serializer_method(
        serializer_or_field=
        "djangocurrency.currencies.serializers.CurrencySerializer"
    )
    def get_currency(self, obj: Country) -> []:
        return obj.currencies()

    @swagger_serializer_method(serializer_or_field=serializers.CharField)
    def get_region(self, obj: Country) -> str:
        """
        Country region wrapper
        :param obj: Country
        """
        return obj.region

    @swagger_serializer_method(serializer_or_field=serializers.CharField)
    def get_subregion(self, obj: Country) -> str:
        """
        Country subregien wrapper
        :param obj: Country
        """
        return obj.subregion

    @swagger_serializer_method(serializer_or_field=serializers.CharField)
    def get_tld(self, obj: Country) -> str:
        """
        Country TLD wrapper
        :param obj: Country
        """
        return obj.tld

    @swagger_serializer_method(serializer_or_field=serializers.CharField)
    def get_capital(self, obj: Country) -> str:
        """
        Country capital wrapper
        :param obj: Country
        """
        return obj.capital

    @swagger_serializer_method(serializer_or_field=serializers.CharField)
    def get_unit_system(self, obj: Country) -> str:
        """
        Country Unit system wrapper
        :param obj: Country
        """
        return obj.unit_system

    @swagger_serializer_method(serializer_or_field=serializers.CharField)
    def get_translated_name(self, obj: Country) -> str:
        """
        Country translation wrapper
        :param obj: Country
        """
        request = self.context.get('request', None)
        if request:
            try:
                language = validate_language(
                    request.GET.get('language',
                                    request.LANGUAGE_CODE))
                translation = gettext.translation(
                    'iso3166', pycountry.LOCALES_DIR,
                    languages=[language])
                translation.install()
                return translation.gettext(obj.name)
            except FileNotFoundError:
                return obj.name
        else:
            return obj.name


class CountrySubdivisionSerializer(serializers.Serializer):
    """
    Serializer for Country
    """
    name = serializers.CharField(
        label="ISO-3166-2 Country subdivision name"
    )
    code = serializers.CharField(
        label="ISO 3166-2 code value"
    )
    type = serializers.CharField(
        label="subdivision type")
    country_code = serializers.CharField(
        label="ISO 3166-1 country code"
    )
    translated_name = serializers.SerializerMethodField(
        label="Translated country subdivision name")

    @staticmethod
    def validate_code(code):
        """
        Validate that code is valid
        :param code: code from IS O3166-2
        """
        if subdivisions.get(code=code):
            return code
        else:
            raise serializers.ValidationError(
                'Invalid country subdivision code')

    def create(self, validated_data) -> CountrySubdivision:
        """
        Create a Country subdivision object
        :param validated_data: cleaned data
        """
        return CountrySubdivision(
            code=validated_data.get('code')
        )

    def update(self, instance, validated_data) -> CountrySubdivision:
        """
        Update a Country object
        :param instance: Country subdivision object
        :param validated_data: cleaned data
        """
        sd = CountrySubdivision(code=validated_data.get('code'))
        self.instance = sd
        return self.instance

    @swagger_serializer_method(serializer_or_field=serializers.CharField)
    def get_translated_name(self, obj: Country) -> str:
        """
        Translate country subdivision name
        :param obj: CountrySubdivision
        :return: translated name
        """
        request = self.context.get('request', None)
        if request:
            try:
                language = validate_language(
                    request.GET.get('language',
                                    request.LANGUAGE_CODE))
                translation = gettext.translation(
                    'iso3166-2', pycountry.LOCALES_DIR,
                    languages=[language])
                translation.install()
                return translation.gettext(obj.name)
            except FileNotFoundError:
                return obj.name
        else:
            return obj.name
