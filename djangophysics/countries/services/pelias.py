"""
Pelias geocoder
"""
import json
import logging

from django.conf import settings
from pycountry import countries

from . import Geocoder, GeocoderRequestError
from ..models import Address
from ..settings import GEOCODING_SERVICE_SETTINGS


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
        try:
            pelias_url = settings.GEOCODER_PELIAS_URL
        except AttributeError:
            pelias_url = GEOCODING_SERVICE_SETTINGS['pelias']['default_url']
        self.server_url = server_url or pelias_url

    def _parse_response(self, response) -> dict:
        """
        Handle response errors
        """
        if response.status_code == 200:
            try:
                return response.json()
            except json.JSONDecodeError as e:
                raise GeocoderRequestError(
                    f"Invalid json response from geocoder: {e}") from e
        elif response.status_code == 400:
            raise GeocoderRequestError(
                f"Invalid geocoder request parameters: {response.content}"
            )
        elif response.status_code == 401:
            raise GeocoderRequestError(
                f"Invalid geocoder credentials: {response.content}"
            )
        elif response.status_code == 404:
            raise GeocoderRequestError(
                f"Invalid geocoder request url: {response.content}"
            )
        elif response.status_code == 429:
            raise GeocoderRequestError(
                f"Too many requests to geocoder: {response.content}"
            )
        elif response.status_code == 500:
            raise GeocoderRequestError(
                f"Geocoder server error: {response.content}"
            )
        return {}

    def search(self,
               address: str,
               key: str = None,
               language: str = None,
               bounds: str = None,
               region: str = None,
               components: str = "") -> dict:
        """
        Search address
        :param address: Address to look for
        :param key: Service API key
        :param language: The language in which to return results.
        :param bounds: Unused at the moment
        :param region: not used
        :param components: not used
        """
        search_args = {'text': address}
        if key:
            search_args['api_key'] = self.key
        return self._query_server(f'{self.server_url}/search', search_args)

    def reverse(self,
                lat: str,
                lng: str,
                key: str = None,
                language: str = None) -> dict:
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
        if key:
            search_args['api_key'] = key
        return self._query_server(f'{self.server_url}/reverse', search_args)

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
                address.location = {
                    'lat': feature['geometry']['coordinates'][0],
                    'lng': feature['geometry']['coordinates'][1],
                }
                address.street_number = feature['properties']['housenumber']
                address.street = feature['properties']['street']
                address.postal_code = feature['properties']['postalcode']
                address.locality = feature['properties']['locality']
                address.county_label = feature['properties'].get(
                    'county',
                    None)
                address.subdivision_code = feature['properties'].get(
                    'region_a',
                    None)
                address.subdivision_label = feature['properties'].get(
                    'region',
                    None)
                address.country_alpha_2 = feature[
                                              'properties'
                                          ]['country_a'][:2]
                addresses.append(address)
            except KeyError as e:
                logging.warning(f'upparsable address {feature}')
        return addresses
