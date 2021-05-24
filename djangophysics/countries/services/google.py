"""
Google Geocoder service
"""
import json
import logging

from django.conf import settings

from . import Geocoder, GeocoderRequestError
from ..models import Address

GEOCODER_GOOGLE_URL = 'https://maps.googleapis.com/maps/api'


class GoogleGeocoder(Geocoder):
    """
    Google geocoder class
    search and reverse from Google
    """
    coder_type = 'google'
    key = None

    def __new__(cls, *args, **kwargs):
        """
        Initialize
        """
        return super(Geocoder, cls).__new__(cls)

    def _parse_response(self, response) -> dict:
        """
        Handle response errors
        """
        if response.status_code == 200:
            try:
                json_response = response.json()
                if json_response['status'] in ('OK', 'ZERO_RESULTS'):
                    return json_response
                elif json_response['status'] in (
                        'OVER_DAILY_LIMIT',
                        'OVER_QUERY_LIMIT'):
                    raise GeocoderRequestError(
                        f"Too many requests to geocoder: "
                        f"{json_response['status']}"
                    )
                elif json_response['status'] == 'REQUEST_DENIED':
                    raise GeocoderRequestError(
                        f"Invalid geocoder credentials: {response.content}"
                    )
                elif json_response['status'] == 'INVALID_REQUEST':
                    raise GeocoderRequestError(
                        f"Invalid geocoder request parameters: "
                        f"{response.content}"
                    )
                elif json_response['status'] == 'UNKNOWN_ERROR':
                    raise GeocoderRequestError(
                        f"Geocoder server error: {response.content}"
                    )
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
               key: str,
               language: str = None,
               bounds: str = None,
               region: str = None,
               components: str = "") -> dict:
        """
        Google geocoding search
        Retrieves coordinates based on address
        """
        search_args = {
            'address': address,
            'key': key,
            'language': language
        }
        return self._query_server(
            f'{GEOCODER_GOOGLE_URL}/geocode/json',
            search_args)

    def reverse(self,
                lat: str,
                lng: str,
                key: str,
                language: str = None) -> dict:
        """
        Google geocoding reverse
        :param lat: latitude
        :param lng: longitude
        :param language: The language in which to return results. 
        """
        search_args = {
            'latlng': ",".join(map(str, [lat, lng])),
            'key': key,
        }
        return self._query_server(
            f'{GEOCODER_GOOGLE_URL}/geocode/json',
            search_args)

    def parse_countries(self, data: dict) -> [str]:
        """
        parse response from google service
        :params data: geocoding / reverse geocoding json
        :return: array of alpha2 codes
        """
        alphas = []
        if not data:
            return alphas
        for feature in data.get('results'):
            for address_component in feature.get('address_components'):
                if 'country' in address_component.get('types'):
                    alphas.append(address_component.get('short_name'))
        return alphas

    def parse_addresses(self, data: dict) -> [Address]:
        """
        Parse address from Pelias response
        """
        addresses = []
        for feature in data.get('results'):
            try:
                address = Address()
                address.location = feature['geometry']['location']
                for component in feature['address_components']:
                    if 'street_number' in component['types']:
                        address.street_number = component['long_name']
                    if 'route' in component['types']:
                        address.street = component['long_name']
                    if 'locality' in component['types']:
                        address.locality = component['long_name']
                    if 'administrative_area_level_2' in component['types']:
                        address.county_label = component['long_name']
                    if 'administrative_area_level_1' in component['types']:
                        address.subdivision_code = component['short_name']
                        address.subdivision_label = component['long_name']
                    if 'country' in component['types']:
                        address.country_alpha_2 = component['short_name']
                    if 'postal_code' in component['types']:
                        address.postal_code = component['long_name']
                addresses.append(address)
            except KeyError as e:
                logging.warning(f'unparsable address {feature}: {str(e)}')
        return addresses
