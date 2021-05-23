"""
Google Geocoder service
"""
import logging

import requests
from django.conf import settings

from . import Geocoder
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

    def __init__(self, key: str = None, *args, **kwargs):
        """
        Google geocode engine
        Init: Geocoder('google', 'API key')
        """
        try:
            if not key and not settings.GEOCODER_GOOGLE_KEY:
                raise ValueError(
                    "This geocoder needs an API key, please provide a key"
                    " or set GEOCODER_GOOGLE_KEY in configuration")
        except AttributeError:
            raise ValueError(
                "This geocoder needs an API key, please provide a key "
                "or set GEOCODER_GOOGLE_KEY in configuration")
        self.key = key or settings.GEOCODER_GOOGLE_KEY

    def search(self, address: str, language: str = None, bounds=None,
               region: str = None, components: str = "") -> dict:
        """
        Google geocoding search
        Retrieves coordinates based on address
        """
        response = requests.get('{}/{}'.format(
            GEOCODER_GOOGLE_URL,
            'geocode/json'
        ), {
            'address': address,
            'key': self.key,
            'language': language
        })
        data = response.json()
        if data.get('status') != "OK":
            print("error", data)
        return data

    def reverse(self, lat: str, lng: str, language: str = None) -> dict:
        """
        Google geocoding reverse
        :param lat: latitude
        :param lng: longitude
        :param language: The language in which to return results. 
        """
        request_data = {
            'latlng': ",".join(map(str, [lat, lng])),
            'key': self.key,
        }
        print(request_data)
        response = requests.get('{}/{}'.format(
            GEOCODER_GOOGLE_URL,
            'geocode/json'
            ), request_data
        )
        data = response.json()
        if data.get('status') != "OK":
            print("error", data)
        return data

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
            print("--feature", feature)
            try:
                address = Address()
                address.location = feature['geometry']['location']
                for component in feature['address_components']:
                    print("component", component)
                    if 'street_number' in component['types']:
                        address.street_number = component['long_name']
                    if 'route' in component['types']:
                        address.street = component['long_name']
                    if 'locality' in component['types']:
                        address.locality = component['long_name']
                    if 'administrative_area_level_2' in component['types']:
                        address.county = component['long_name']
                    if 'administrative_area_level_1' in component['types']:
                        address.subdivision = component['short_name']
                        address.subdivision_label = component['long_name']
                    if 'country' in component['types']:
                        address.country = component['short_name']
                    if 'postal_code' in component['types']:
                        address.postal_code = component['long_name']
                print(address)
                addresses.append(address)
            except KeyError as e:
                print(e)
                print(f'unparsable address {feature}')
                logging.warning(f'unparsable address {feature}: {str(e)}')
        return addresses
