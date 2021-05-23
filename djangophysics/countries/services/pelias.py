"""
Pelias geocoder
"""
import logging

import requests
from django.conf import settings
from pycountry import countries

from . import Geocoder
from ..settings import GEOCODING_SERVICE_SETTINGS
from ..models import Address


class PeliasGeocoder(Geocoder):
    """
    Pelias geocoder
    """
    coder_type = 'pelias'
    server_url = None
    key = None

    def __new__(cls, *args, **kwargs):
        """
        Initialize
        """
        return super(Geocoder, cls).__new__(cls)

    def __init__(self, server_url: str = None, key: str = None,
                 *args, **kwargs):
        """
        Init pelias geocoder
        Init: Geocoder('pelias', server_url='serveur URL', key='API key')
        :params server_url: Custom pelias URL,
        defaults to 'https://api.geocode.earth/v1/search'
        :param key: API key
        """
        self.key = key or settings.GEOCODER_PELIAS_KEY
        try:
            pelias_url = settings.GEOCODER_PELIAS_URL
        except AttributeError:
            pelias_url = GEOCODING_SERVICE_SETTINGS['pelias']['default_url']
        self.server_url = server_url or pelias_url

    def search(self, address: str, language: str = None,
               bounds: str = None, region: str = None,
               components: str = "") -> dict:
        """
        Search address
        :param address: Address to look for
        :param language: The language in which to return results.
        :param bounds: Unused at the moment
        :param region: not used
        :param components: not used
        """
        search_args = {'text': address}
        if self.key:
            search_args['api_key'] = self.key
        try:
            response = requests.get(f'{self.server_url}/search', search_args)
            data = response.json()
            if 'errors' in data:
                logging.error("Invalid request")
                logging.error(data.get('error'))
                return {}
            return data
        except ValueError as e:
            logging.error("Invalid API configuration")
            logging.error(e)
        except IOError as e:
            logging.error("Invalid request")
            logging.error(e)
        return {}

    def reverse(self, lat: str, lng: str, language: str = None) -> dict:
        """
        Reverse search by coordinates
        :param lat: latitude
        :param lng: longitude
        :param language: The language in which to return results.
        """
        search_args = {
            'point.lat': lat,
            'point.lon': lng,
        }
        if self.key:
            search_args['api_key'] = self.key
        try:
            response = requests.get(f'{self.server_url}/reverse', search_args)
            data = response.json()
            if 'errors' in data:
                logging.error("ERROR - Invalid request")
                logging.error(data.get('error'))
                return {}
            return data
        except ValueError as e:
            logging.error("Invalid API configuration")
            logging.error(e)
        except IOError as e:
            logging.error("Invalid request", e)
        return {}

    def parse_countries(self, data: dict) -> [str]:
        """
        parse response from google service
        :params data: geocoding / reverse geocoding json
        :return: array of alpha2 codes
        """
        alphas = []
        if not data:
            return alphas
        for feature in data.get('features'):
            alphas.append(countries.get(
                alpha_3=feature.get('properties'
                                    ).get('country_a')).alpha_2)
        return alphas

    def parse_addresses(self, data: dict) -> [Address]:
        """
        Parse address from Pelias response
        """
        addresses = []
        for feature in data.get('features'):
            address = Address()
            try:
                address.location = feature['geometry']['coordinates']
                address.street_number = feature['properties']['housenumber']
                address.street = feature['properties']['street']
                address.postal_code = feature['properties']['postalcode']
                address.locality = feature['properties']['locality']
                address.county = feature['properties'].get('county', None)
                address.subdivision = feature['properties'].get('region_a', None)
                address.country = feature['properties']['country_a']
                addresses.append(address)
            except KeyError as e:
                logging.warning(f'upparsable address {feature}')
        return



