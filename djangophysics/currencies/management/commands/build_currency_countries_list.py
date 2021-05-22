"""
Command to build data.pyy file with a correspondence
between a currency and the countries using it using
CountryInfo library
"""
import json
import os

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """
    Fetch rates command
    """
    help = 'Fetch rates for a date'

    def handle(self, *args, **options):
        """
        Handle call
        """
        datafile = os.path.join(
            os.path.dirname(__file__),
            '..',
            '..',
            'data.py')
        currency_countries = {}
        from countryinfo import CountryInfo
        ci = CountryInfo()
        for value in ci.all().values():
            for currency in value.get('currencies', []):
                if currency in currency_countries:
                    currency_countries[currency].append(value['ISO']['alpha2'])
                else:
                    currency_countries[currency] = [value['ISO']['alpha2'],]
        with open(datafile, "w") as fp:
            fp.write(
                f"CURRENCY_COUNTRIES = "
                f"{json.dumps(currency_countries, indent=2)}\n"
            )
