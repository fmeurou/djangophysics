"""
Models for Country module
"""

import logging
import os
import re
from datetime import datetime

import pytz
import requests
from countryinfo import CountryInfo
from django.conf import settings
from django.core.cache import caches, cache
from django.db import models
from pycountry import countries, subdivisions
from pytz import timezone

from .helpers import ColorProximity, hextorgb
from .settings import FLAG_SOURCE


class CountryNotFoundError(Exception):
    """
    Exception when Country is not found
    """
    msg = 'Country not found'


class CountryManager(models.Manager):
    """
    Manager for country model
    """

    @staticmethod
    def get_by_color(color, proximity=1):
        """
        Take a hex color and finds near country
        based on flag and color proximity
        :param color: hex color (FFF, FFFFFF,
         FFFFFFFF, #FFF, #FFFFFF, #FFFFFFFF)
        :param proximity: succes rate, positive
         if below (100 is opposite, 0 is identical
        """
        cp = ColorProximity()
        rgb_color = hextorgb(color)
        ctrs = []
        for country in Country.objects.filter(colors__isnull=False):
            for fc in country.colors.split(','):
                flag_color = hextorgb(fc)
                if cp.proximity(rgb_color, flag_color) < proximity:
                    ctrs.append(country.pk)
                    break
        return Country.objects.filter(pk__in=set(ctrs))


class Country:
    """
    Country class
    Wrapper around pycountry object
    """
    # data extracted from pycountry as basic data
    # if CountryInfo for this country does not exist
    alpha_2 = None
    alpha_3 = None
    name = None
    numeric = None

    def __init__(self, alpha_2):
        """
        Init a Country object with an alpha2 code
        :params country_name: ISO-3166 alpha_2 code
        """
        country = countries.get(alpha_2=alpha_2)
        if not country:
            raise CountryNotFoundError("Invalid country alpha2 code")
        self.alpha_2 = country.alpha_2
        self.alpha_3 = country.alpha_3
        self.name = country.name
        self.numeric = country.numeric

    @classmethod
    def search(cls, term: str) -> []:
        """
        Search for Contruy by name, alpha_2, alpha_3, or numeric value
        :param term: Search term
        """
        result = []
        for attr in ['alpha_2', 'alpha_3', 'name', 'numeric']:
            result.extend(
                [getattr(c, 'alpha_2') for c in countries
                 if term.lower() in getattr(c, attr).lower()]
            )
        return sorted([Country(r) for r in set(result)], key=lambda x: x.name)

    @classmethod
    def all_countries(cls, ordering: str = 'name'):
        """
        List all countries, instanciate CountryInfo
        for each country in pycountry.countries
        :param ordering: sort list
        """
        descending = False
        if ordering and ordering[0] == '-':
            ordering = ordering[1:]
            descending = True
        if ordering not in ['name', 'alpha_2', 'alpha_3', 'numeric']:
            ordering = 'name'
        return list(sorted(map(lambda x: cls(x.alpha_2), countries),
                           key=lambda x: getattr(x, ordering),
                           reverse=descending))

    def base(self):
        """
        Returns a basic representation of a country with name and iso codes
        """
        return countries.get(alpha_2=self.alpha_2)._fields

    def currencies(self, *args, **kwargs) -> []:
        """
        Return a list of currencies used in this country
        """
        from djangophysics.currencies.models import Currency
        from djangophysics.currencies.models import CurrencyNotFoundError
        ci = CountryInfo(self.alpha_2)
        currencies = []
        for currency in ci.currencies():
            try:
                currencies.append(Currency(code=currency))
            except CurrencyNotFoundError:
                pass
        return currencies

    @property
    def unit_system(self) -> str:
        """
        Return UnitSystem for country
        """
        if self.alpha_2 == 'US':
            return 'US'
        if self.alpha_2 == 'LR':
            return 'US'
        if self.alpha_2 == 'MM':
            return 'imperial'
        return 'SI'

    @property
    def timezones(self) -> []:
        """
        Returns a list of timezones for a country
        """
        output = []
        fmt = '%z'
        base_time = datetime.utcnow()
        for tz_info in pytz.country_timezones[self.alpha_2]:
            tz = timezone(tz_info)
            offset = tz.localize(base_time).strftime(fmt)
            numeric_offset = float(offset[:-2] + '.' + offset[-2:])
            output.append({
                'name': tz_info,
                'offset': f'UTC {offset}',
                'numeric_offset': numeric_offset,
                'current_time': base_time.astimezone(
                    tz).strftime('%Y-%m-%d %H:%M')
            })
        return sorted(output, key=lambda x: x['numeric_offset'])

    @property
    def flag_path(self):
        """
        Path to the flag temporary file
        :return: string, absolute path to the flag file
        """
        return os.path.join(settings.MEDIA_ROOT, self.alpha_2 + '.svg')

    def flag_exists(self):
        """
        Checks if flag file exists
        :return: bool, True if flag exists, False otherwise
        """
        return os.path.exists(self.flag_path)

    def download_flag(self):
        """
        Downloads flag for country in temporary path
        :return: Path to the file
        """
        if not self.flag_exists():
            response = requests.get(FLAG_SOURCE.format(alpha_2=self.alpha_2))
            try:
                flag_content = response.text
                flag_file = open(self.flag_path, 'w')
                flag_file.write(flag_content)
                flag_file.close()
                return self.flag_path
            except IOError:
                logging.error(f"unable to write file {self.flag_path}")
                return None

    def analyze_flag(self):
        """
        Analyze colors of the flag for the country and caches the result
        :returns: array, list of colors
        """
        flag_path = os.path.join(settings.MEDIA_ROOT, self.alpha_2 + '.svg')
        # Checks if flag has been downloaded, downloads it otherwise,
        # and return None if download failed
        if not self.flag_exists() and not self.download_flag():
            return None
        with open(flag_path, 'r') as flag:
            content = flag.read()
            result = re.findall(r'\#[0-9A-Fa-f]{1,2}[0-9A-Fa-f]'
                                r'{1,2}[0-9A-Fa-f]{1,2}', content)
            if result:
                cache.set('COLORS-' + self.alpha_2, result)
            return result

    def colors(self):
        """
        List colors present in the flag of the country
        :returns: array, list of colors
        """
        colors = cache.get('COLORS-' + self.alpha_2)
        if colors:
            return colors
        else:
            return self.analyze_flag()

    @property
    def info(self) -> str:
        """
        Return country region
        """
        try:
            ccache = caches['countries']
        except KeyError:
            ccache = cache
        if not ccache.get(self.alpha_2):
            try:
                info = CountryInfo(self.alpha_2).info()
            except KeyError:
                info = {}
            ccache.set(self.alpha_2, info)
        return ccache.get(self.alpha_2) or {}

    @property
    def region(self) -> str:
        """
        Return country region
        """
        return self.info.get('region', '')

    @property
    def subregion(self) -> str:
        """
        Return country subregion
        """
        return self.info.get('subregion', '')

    @property
    def tld(self) -> str:
        """
        Return country TLD
        """
        return self.info.get('tld', '')

    @property
    def capital(self) -> str:
        """
        Return country capital
        """
        return self.info.get('capital', '')

    @property
    def population(self) -> int:
        """
        Return country population
        """
        try:
            return int(self.info.get('population', ''))
        except ValueError:
            return 0

    def subdivisions(self, *args, search_term=None, ordering='name'):
        """
        List ISO 3166-2 subdivisions of a country
        """
        return CountrySubdivision.list_for_country(
            country_code=self.alpha_2,
            search_term=search_term,
            ordering=ordering
        )


class CountrySubdivisionNotFound(Exception):
    """
    Exception when the subdivision cannot be found
    """
    pass


class CountrySubdivision:
    code = None
    name = None
    type = None
    country_code = None
    parent_code = None

    def __init__(self, code):
        try:
            sd = subdivisions.get(code=code)
        except LookupError as e:
            raise CountrySubdivisionNotFound(str(e)) from e
        if not sd:
            raise CountrySubdivisionNotFound(
                f"Subdivision {code} does not exist"
            )
        self.code = code
        self.name = sd.name
        self.type = sd.type
        self.country_code = sd.country_code
        self.parent_code = sd.parent_code

    @classmethod
    def list_for_country(cls, country_code, search_term=None, ordering='name'):
        if ordering not in ['code', 'name', 'type']:
            ordering = 'name'
        if search_term:
            return cls.search(
                search_term=search_term,
                country_code=country_code,
                ordering=ordering
            )
        else:
            try:
                return sorted([CountrySubdivision(code=r.code)
                               for r in subdivisions.get(country_code=country_code)],
                              key=lambda x: getattr(x, ordering))
            except TypeError as e:
                raise CountrySubdivisionNotFound(str(e)) from e

    @classmethod
    def search(cls, search_term, ordering='name', country_code=None):
        if ordering not in ['code', 'name', 'type']:
            ordering = 'name'
        result = []
        search_term = search_term or ''
        for attr in ['code', 'name', 'type']:
            if country_code:
                result.extend(
                    [getattr(sd, 'code') for sd in subdivisions
                     if search_term.lower() in getattr(sd, attr).lower()
                     and sd.country_code.lower() == country_code.lower()]
                )
            else:
                result.extend(
                    [getattr(sd, 'code') for sd in subdivisions
                     if search_term.lower() in getattr(sd, attr).lower()]
                )
        return sorted([CountrySubdivision(code=r) for r in set(result)],
                      key=lambda x: getattr(x, ordering))

    @property
    def country(self):
        """
        Return the Country object corresponding to the country code
        """
        return Country(alpha_2=self.country_code)

    @property
    def parent(self):
        """
        Return the CountrySubdivision object corresponding to the parent_code
        """
        if self.parent_code:
            return CountrySubdivision(code=self.parent_code)
        return None

    def children(self, *args, search_term: str = None, ordering: str = 'name'):
        """
        List children of the subdivision
        """
        if ordering not in ['code', 'name', 'type']:
            ordering = 'name'
        if search_term:
            return sorted(
                [CountrySubdivision(code=sd.code)
                 for sd in self.search(search_term=search_term)
                 if sd.parent_code == self.code and
                 sd.country_code == self.country_code],
                key=lambda x: getattr(x, ordering))
        else:
            return sorted(
                [CountrySubdivision(code=sd.code)
                 for sd in self.list_for_country(country_code=self.country_code)
                 if sd.parent_code == self.code],
                key=lambda x: getattr(x, ordering))


class Location:
    """
    GPS Location
    """
    latitude = None  # type: float
    longitude = None # type: float


class Address:
    """
    Geocoder address
    location: GPS coordinates [lat, lng]
    street number
    street: Name of the street
    postal_code
    city: Name of the city
    subdivision: ISO 3166-2 code
    country: ISO 3166-1 alpha2
    confidence: Int representing confidence in geolocation
    """
    location = None  # type: Location
    street_number = None  # type: str
    street = None  # type: str
    postal_code = None  # type: str
    locality = None  # type: str
    county_label = None  # type: str
    subdivision_label = None  # type: str
    subdivision_code = None  # type: str
    country_alpha_2 = None  # type: str
    confidence = 0

    def save(self):
        cache.set(self.location, self)

    @classmethod
    def load(cls, location):
        return cache.get(location)

    @property
    def county(self):
        if self.county_label:
            sd = CountrySubdivision.search(
                search_term=self.county_label,
                country_code=self.country_alpha_2)
            if sd:
                return sd[0]
        return None

    @property
    def subdivision(self):
        if self.subdivision_label:
            sd = CountrySubdivision(
                code=f"{self.country_alpha_2}-{self.subdivision_code}"
            )
            if sd:
                return sd
        return None

    @property
    def country(self):
        return Country(alpha_2=self.country_alpha_2)

