"""
Models for Country module
"""

import csv
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

    @classmethod
    def countries_for_region(cls, region: str):
        """
        List countries for a specific region
        :param region: name of the region
        """
        ci = CountryInfo()
        return [c['ISO']['alpha2'] for c in ci.all().values() if 'europe' in c.get('region', '').lower()]

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
                'current_time': base_time.astimezone(tz).strftime('%Y-%m-%d %H:%M')
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

    @staticmethod
    def regions() -> []:
        """
        List of regions
        """
        return ['Africa', 'Americas', 'Asia', 'Europe', 'Oceania']


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
    longitude = None  # type: float


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


class RegionData:
    __instance__ = None

    @classmethod
    def instance(cls):
        if not cls.__instance__:
            cls.__instance__ = cls.RegionDataPrivate()
        return cls.__instance__

    def __getattr__(self, item):
        if item == 'region_data':
            return self.__instance__.region_data
        elif item == 'subregion_data':
            return self.__instance__.region_data
        elif item == 'country_data':
            return self.__instance__.country_data
        else:
            return super().__getattr__(item)

    class RegionDataPrivate:
        region_data = {}
        region_names = []
        subregion_data = {}
        subregion_names = []
        country_data = {}
        COLUMNS = {
            'region_code': 2,
            'region_name': 3,
            'subregion_code': 4,
            'subregion_name': 5,
            'country_alpha2': 10
        }

        def __init__(self):
            """
            Initiate load of data
            """
            filename = 'unsd_methodology.csv'
            data_dir = os.path.dirname(os.path.abspath(__file__))
            source_file = os.path.join(data_dir, 'data', filename)
            region_names = []
            subregions_names = []
            first_line = True
            with open(source_file) as source_csv:
                reader = csv.reader(source_csv)
                for line in reader:
                    if first_line:
                        first_line = False
                        continue
                    self.parse_region(line=line)
                    self.parse_subregion(line=line)
                    self.parse_countries(line=line)
                    if line[self.COLUMNS['region_name']]:
                        region_names.append(line[self.COLUMNS['region_name']])
                    if line[self.COLUMNS['subregion_name']]:
                        subregions_names.append(region_names.append(line[self.COLUMNS['subregion_name']]))

            self.region_names = set(region_names)
            self.subregion_names = set(subregions_names)

        def parse_region(self, line):
            """
            Parse region from CSV
            """
            if not line[self.COLUMNS['region_name']]:
                return
            if line[self.COLUMNS['region_name']] not in self.region_data:
                self.region_data[line[self.COLUMNS['region_name']]] = {
                    'code': line[self.COLUMNS['region_code']],
                    'name': line[self.COLUMNS['region_name']],
                    'subregions': [line[self.COLUMNS['subregion_code']], ],
                    'countries': [line[self.COLUMNS['country_alpha2']], ]
                }
            else:
                self.region_data[line[self.COLUMNS['region_name']]]['countries'].append(line[self.COLUMNS['country_alpha2']])
                self.region_data[line[self.COLUMNS['region_name']]]['subregions'].append(line[self.COLUMNS['subregion_code']])
            self.region_data[line[self.COLUMNS['region_code']]] = self.region_data[line[self.COLUMNS['region_name']]]

        def parse_subregion(self, line):
            """
            Parse subregions from CSV
            """
            if not line[self.COLUMNS['subregion_name']]:
                return
            if line[self.COLUMNS['subregion_name']] not in self.subregion_data:
                self.subregion_data[line[self.COLUMNS['subregion_name']]] = {
                    'region': {
                        'code': line[self.COLUMNS['region_code']],
                        'name': line[self.COLUMNS['region_name']]
                    },
                    'code': line[self.COLUMNS['subregion_code']],
                    'name': line[self.COLUMNS['subregion_name']],
                    'countries': [line[self.COLUMNS['country_alpha2']], ]
                }
            else:
                self.subregion_data[line[self.COLUMNS['subregion_name']]]['countries'].append(
                    line[self.COLUMNS['country_alpha2']])
            self.subregion_data[line[self.COLUMNS['subregion_code']]] = self.subregion_data[line[self.COLUMNS['subregion_name']]]

        def parse_countries(self, line):
            """
            parse countries from CSV
            :param line: line from CSV
            """
            if not line[self.COLUMNS['country_alpha2']]:
                return

            self.country_data[line[self.COLUMNS['country_alpha2']]] = {
                'region': {
                    'code': line[self.COLUMNS['region_code']],
                    'name': line[self.COLUMNS['region_name']]
                },
                'subregion': {
                    'code': line[self.COLUMNS['subregion_code']],
                    'name': line[self.COLUMNS['subregion_name']]
                }
            }


class InvalidRegionName(Exception):
    message = "Invalid region or subregion name"


class Region:
    name = None
    code = None
    type = None
    _parent = None
    _country_list = None
    _data = None

    def __init__(self, key):
        region_data = RegionData.instance()
        if key in region_data.region_data:
            self.get_region(key=key)
        elif key in region_data.subregion_data:
            self.get_subregion(key=key)
        else:
            raise InvalidRegionName(f"Region not found: {key}")

    @classmethod
    def all_regions(cls, ordering: str='name'):
        region_data = RegionData.instance()
        output = cls._all_regions(region_data.region_data)
        return sorted(output, key=lambda x: getattr(x, ordering))

    @classmethod
    def all_subregions(cls, ordering: str='name'):
        region_data = RegionData.instance()
        output = cls._all_regions(region_data.subregion_data)
        return sorted(output, key=lambda x: getattr(x, ordering))

    @classmethod
    def _all_regions(cls, data):
        output = []
        codes = []
        for key in data:
            if key:
                region = Region(key=key)
                if region.code not in codes:
                    output.append(region)
                    codes.append(region.code)
        return output

    def get_region(self, key: str):
        """
        Get a Region from code or name
        :param key: Name or code of the region
        """
        region_data = RegionData.instance()
        region = region_data.region_data[key]
        self.name = region.get('name')
        self.code = region.get('code')
        self.type = 'region'
        self._parent = None
        self._country_list = region.get('countries')

    def get_subregion(self, key):
        """
        Get a SubRegion from code or name
        :param key: Name or code of the subregion
        """
        region_data = RegionData.instance()
        subregion = region_data.subregion_data[key]
        self.name = subregion.get('name')
        self.code = subregion.get('code')
        self.type = 'subregion'
        self._parent = subregion['region']['name']
        self._country_list = subregion.get('countries')

    def parent(self, *args, **kwargs):
        """
        Return the parent Region object
        """
        if self.parent:
            return Region(key=self._parent)
        return None

    def subregions(self, *args, **kwargs):
        region_data = RegionData.instance()
        return set([Region(sr.get('code')) for sr in region_data.subregion_data.values()
                if sr.get('region', {}).get('code') == self.code
                ])

    def countries(self, *args, **kwargs):
        region_data = RegionData.instance()
        return [Country(alpha_2=c) for c in self._country_list if c]

    @classmethod
    def region_for_country(cls, alpha_2):
        region_data = RegionData.instance()
        if alpha_2 in region_data.country_data:
            return cls(key=region_data.country_data[alpha_2]['region']['code'])
        return None

    @classmethod
    def subregion_for_country(cls, alpha_2):
        region_data = RegionData.instance()
        if alpha_2 in region_data.country_data:
            return cls(key=region_data.country_data[alpha_2]['subregion']['code'])
        return None

    @classmethod
    def search(cls, term: str, ordering: str='name') -> []:
        """
        Search for regions and subregions
        :param term: Search term
        :param ordering: order results
        """
        if ordering not in ['name', 'code', 'type']:
            ordering = 'name'
        region_data = RegionData.instance()
        return sorted(
                [cls(key) for key in region_data.region_data
                 if term.lower() in key.lower()] + \
                [cls(key) for key in region_data.subregion_data
                 if term.lower() in key.lower()],
            key=lambda x: getattr(x, ordering))
