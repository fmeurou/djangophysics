"""
Serializers for Currencies module
"""
import datetime

from drf_yasg.utils import swagger_serializer_method
from rest_framework import serializers

from djangophysics.countries.models import Country
from djangophysics.countries.serializers import CountryDetailSerializer
from djangophysics.currencies.models import Currency
from djangophysics.currencies.serializers import CurrencySerializer


class CountryDetailWithCurrenciesSerializer(CountryDetailSerializer):
    pass


class RateWithCurrencySerializer(serializers.Serializer):
    pass


class CurrencyWithCountriesSerializer(CurrencySerializer):
    """
    Serializer for CurrencyClass with countries
    """
    countries = CountryDetailWithCurrenciesSerializer(
        label="List of countries where currency applies",
        many=True)
    # rates_from = RateWithCurrencySerializer(
    #     label="List of rates for this currency"
    # )
    # rates_to = RateWithCurrencySerializer(
    #     label="List of rates for this currency"
    # )


class CountryDetailWithCurrenciesSerializer(CountryDetailSerializer):
    """
    Detailed Serializer for Country
    """
    currencies = CurrencyWithCountriesSerializer(many=True,
                                                 label="Currencies for this country")

    @swagger_serializer_method(serializer_or_field=CurrencySerializer)
    def get_currencies(self, obj: Country) -> []:
        return obj.currencies()


class RateWithCurrencySerializer(serializers.Serializer):
    base_currency = serializers.SerializerMethodField(
        label="Currency rates converts into",
    )
    currency = serializers.SerializerMethodField(
        label="Currency rates converts from"
    )
    value = serializers.FloatField(
        label="Value of the conversion rate"
    )
    value_date = serializers.DateField(
        label="Date of the conversion value"
    )

    @swagger_serializer_method(serializer_or_field=CurrencyWithCountriesSerializer)
    def get_base_currency(self, obj):
        start = datetime.datetime.now()
        print(f"get base currency for {obj}")
        data =  CurrencyWithCountriesSerializer(Currency(code=obj.base_currency)).data
        end = datetime.datetime.now()
        print(f"data obtained in {end - start}")
        return data

    @swagger_serializer_method(serializer_or_field=CurrencyWithCountriesSerializer)
    def get_currency(self, obj):
        start = datetime.datetime.now()
        print(f"get currency for {obj}")
        data = CurrencyWithCountriesSerializer(Currency(code=obj.currency)).data
        end = datetime.datetime.now()
        print(f"data obtained in {end - start}")
        return data
