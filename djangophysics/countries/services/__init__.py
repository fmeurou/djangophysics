"""
Country services
"""
import requests
from timezonefinder import TimezoneFinder

from djangophysics.countries.models import Country, CountryNotFoundError

tf = TimezoneFinder(in_memory=True)


class GeocoderRequestError(Exception):
    """
    Exception to handle returns from servers
    """


class Geocoder:
    """
    Geocoder services
    """

    def _query_server(self, url: str, search_args: dict):
        """
        Internal function to query geocoding server
        """
        response = requests.get(url, search_args)
        return self._parse_response(response=response)

    def _parse_response(self, response) -> dict:
        """
        Handle response errors
        """
        raise NotImplementedError("Use specific implementation")

    def search(self,
               address: str,
               key: str = None,
               language: str = None,
               bounds: str = None,
               region: str = None,
               components: str = "") -> []:
        """
        Search an address
        :param address: address to search for
        :param key: Key to Service
        :param language: optional, language of result
        :param bounds: optional, limit results to bounds
        :param region: optional, limit results to region
        :param components: optional, a components filter
         with elements separated by a pipe (|)
        :returns: [Address]
        """
        raise NotImplementedError("Use specific implementation")

    def reverse(self, lat: float, lng: float, key: str = None, language: str = None):
        """
        Search from GPS coordinates
        :param lat: latitude
        :param lng: longitude
        :param key: Key to Service
        :param language: language of the response
        """
        raise NotImplementedError("Use specific implementation")

    def parse_countries(self, data: dict):
        """
        Parse countries from result
        :params data: geocoding / reverse geocoding result
        :returns: Country instance
        """
        raise NotImplementedError("Use specific implementation")

    def countries(self, data: dict):
        """
        List countries
        :params data: json response from geocoding / reverse geocoding service
        """
        countries = []
        alphas = self.parse_countries(data=data)
        for alpha in set(alphas):
            try:
                if len(alpha) == 2:
                    country = Country(alpha)
                elif len(alpha) == 3:
                    country = Country(alpha[0:2])
                else:
                    country = Country(alpha)
            except CountryNotFoundError:
                continue
            countries.append(country)
        return sorted(countries, key=lambda x: x.name)

    def parse_addresses(self, data: dict):
        """
        Return address
        """
        raise NotImplementedError("Use specific implementation")

    def addresses(self, data: dict):
        """
        List addresses
        :param data: json response from geocoding / reverse geocoding service
        """
        return self.parse_addresses(data=data)
