"""
Country tests
"""
import os

from django.conf import settings
from django.test import TestCase
from pycountry import countries
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APIClient

from djangophysics.core.helpers import service
from .models import Country, CountrySubdivision, CountrySubdivisionNotFound
from .serializers import CountrySerializer, CountrySubdivisionSerializer, \
    AddressSerializer
from .services import GeocoderRequestError
from .services.google import GoogleGeocoder
from .services.pelias import PeliasGeocoder

PELIAS_TEST_URL = 'https://api.geocode.earth/v1'
TEST_ADDRESS = "Rue du Maine, 75014 Paris"
TEST_LAT = 48.763434
TEST_LNG = 2.308702


class TestResponse(Response):
    content = None
    status_code = None
    content_type = None

    def __init__(self, content, status: int = 200,
                 content_type: str = "application/json"):
        self.content = content
        self.status_code = status
        self.content_type = content_type

    def json(self):
        return self.content


class CountryTestCase(TestCase):
    """
    Test Country object
    """

    def setUp(self) -> None:
        """
        Set test up
        """
        settings.GEOCODING_SERVICE = 'google'
        settings.GEOCODER_GOOGLE_KEY = os.environ.get('GOOGLE_API_KEY')
        settings.GEOCODER_PELIAS_KEY = os.environ.get('PELIAS_API_KEY')

    def test_all(self):
        """Numbers of countries is equal to number
        of countries in pycountry.countries"""
        all_countries = Country.all_countries()
        self.assertEqual(len(list(all_countries)), len(countries))

    def test_sorted_all(self):
        """Numbers of countries is equal to number
        of countries in pycountry.countries"""
        self.assertEqual(len(list(Country.all_countries())),
                         len(countries))
        self.assertEqual(Country.all_countries(ordering='name')[-1].alpha_2,
                         'AX')
        self.assertEqual(Country.all_countries(ordering='alpha_2')[-1].alpha_2,
                         'ZW')
        self.assertEqual(Country.all_countries(ordering='alpha_3')[-1].alpha_2,
                         'ZW')
        self.assertEqual(Country.all_countries(ordering='numeric')[-1].alpha_2,
                         'ZM')
        self.assertEqual(
            Country.all_countries(ordering='brouzouf')[-1].alpha_2,
            'AX')

    def test_base(self):
        """
        Basic representation contains name and iso codes
        """
        country = Country("FR")
        self.assertIn("name", country.base())
        self.assertIn("alpha_2", country.base())
        self.assertIn("alpha_3", country.base())
        self.assertIn("numeric", country.base())
        self.assertEqual(country.base().get('name'), 'France')
        self.assertEqual(country.base().get('alpha_2'), 'FR')
        self.assertEqual(country.base().get('alpha_3'), 'FRA')
        self.assertEqual(country.base().get('numeric'), '250')
        self.assertEqual(country.unit_system, 'SI')

    def test_unit_system(self):
        """
        Check unit systems (only US and UK have strange unit systems
        """
        self.assertEqual(Country('FR').unit_system, 'SI')
        self.assertEqual(Country('US').unit_system, 'US')
        self.assertEqual(Country('LR').unit_system, 'US')
        self.assertEqual(Country('MM').unit_system, 'imperial')

    def test_flag_path(self):
        """
        Looking for flags
        """
        country = Country('FR')
        self.assertEqual(country.flag_path,
                         os.path.join(settings.MEDIA_ROOT,
                                      country.alpha_2 + '.svg'))

    def test_flag_exists_and_download(self):
        """
        Testing that flag can be downloaded
        """
        country = Country('FR')
        os.remove(country.flag_path)
        self.assertFalse(country.flag_exists())
        self.assertIsNotNone(country.download_flag())
        self.assertTrue(country.flag_exists())

    def test_colors(self):
        """
        Testing colors have been parsed
        """
        country = Country('FR')
        self.assertIsNotNone(country.colors())

    def test_subdivisions(self):
        """
        Test list of subdivisions per country
        """
        country = Country('FR')
        self.assertEqual(len(country.subdivisions()), 125)
        self.assertEqual(len(country.subdivisions(search_term='FR-PDL')), 1)


class CountryAPITestCase(TestCase):
    """
    Country API tests
    """

    def setUp(self) -> None:
        """
        Set test up
        """
        settings.GEOCODING_SERVICE = 'google'
        settings.GEOCODER_GOOGLE_KEY = os.environ.get('GOOGLE_API_KEY')
        settings.GEOCODER_PELIAS_KEY = os.environ.get('PELIAS_API_KEY')

    def test_list_request(self):
        """
        Testing the list of countries
        """
        client = APIClient()
        response = client.get('/countries/', format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), len(Country.all_countries()))
        self.assertEqual(response.data[0].get('alpha_2'), 'AF')

    def test_list_sorted_name_request(self):
        """
        testing name ordering on List API
        """
        client = APIClient()
        response = client.get(
            '/countries/',
            data={'ordering': 'name'},
            format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), len(Country.all_countries()))
        self.assertEqual(response.data[-1].get('alpha_2'), 'AX')

    def test_list_sorted_numeric_request(self):
        """
        testing numeric ordering on List API
        """
        client = APIClient()
        response = client.get(
            '/countries/',
            data={'ordering': 'numeric'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), len(Country.all_countries()))
        self.assertEqual(response.data[-1].get('alpha_2'), 'ZM')

    def test_retrieve_request(self):
        """
        Testing retieve on country
        """
        client = APIClient()
        response = client.get('/countries/US/', format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        cs = CountrySerializer(data=response.json())
        self.assertTrue(cs.is_valid())
        country = cs.create(cs.validated_data)
        self.assertEqual(country.name, 'United States')
        self.assertEqual(country.region, 'Americas')
        self.assertEqual(country.subregion, 'Northern America')
        self.assertEqual(country.unit_system, 'US')

    def test_google_geocode_request(self):
        """
        Testing geocoding from google
        """
        if settings.GEOCODER_GOOGLE_KEY:
            client = APIClient()
            response = client.get(
                '/countries/geocode/',
                data={'address': TEST_ADDRESS,
                      'key': settings.GEOCODER_GOOGLE_KEY},
                format='json')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
        else:
            print("GEOCODER_GOOGLE_KEY not set, skipping test")

    def test_google_reverse_request(self):
        """
        Testing reverse from google
        """
        if settings.GEOCODER_GOOGLE_KEY:
            client = APIClient()
            response = client.get(
                '/countries/reverse/',
                data={'latitude': TEST_LAT, 'longitude': TEST_LNG,
                      'key': settings.GEOCODER_GOOGLE_KEY},
                format='json')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
        else:
            print("GEOCODER_GOOGLE_KEY not set, skipping test")

    def test_timezones_request(self):
        """
        Testing timezone information
        """
        client = APIClient()
        response = client.get('/countries/FR/timezones/', format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_currencies_request(self):
        """
        Testing currencies information
        """
        client = APIClient()
        response = client.get('/countries/FR/currencies/', format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, "EUR")

    def test_provinces_request(self):
        """
        Testing provingces information
        """
        client = APIClient()
        response = client.get('/countries/FR/provinces/', format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, "Alsace")

    def test_languages_request(self):
        """
        Testing languages information
        """
        client = APIClient()
        response = client.get('/countries/FR/languages/', format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, "fr")

    def test_colors_request(self):
        """
        Testing colors information
        """
        client = APIClient()
        response = client.get('/countries/FR/colors/', format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_borders_request(self):
        """
        Testing borders information
        """
        client = APIClient()
        response = client.get('/countries/FR/borders/', format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, "DEU")


class PeliasGeocoderTest(TestCase):

    def setUp(self):
        self.response = {
            'type': 'FeatureCollection',
            'features': [
                {
                    'type': 'Feature',
                    'geometry': {
                        'type': 'Point',
                        'coordinates': [
                            151.215353,
                            -33.860194
                        ]
                    },
                    'properties': {
                        'layer': 'address',
                        'source': 'openaddresses',
                        'name': '2A Macquarie Street',
                        'housenumber': '2A',
                        'street': 'Macquarie Street',
                        'postalcode': '2000',
                        'confidence': 1,
                        'match_type': 'exact',
                        'accuracy': 'point',
                        'country': 'Australia',
                        'country_a': 'AUS',
                        'region': 'New South Wales',
                        'region_a': 'NSW',
                        'county_a': 'SY',
                        'locality': 'Sydney',
                        'label': '2A Macquarie Street, Sydney, NSW, Australia'
                    }
                }]
        }

        self.BAD_REQUEST = TestResponse("", status=status.HTTP_400_BAD_REQUEST)
        self.UNAUTHORIZED = TestResponse("",
                                         status=status.HTTP_401_UNAUTHORIZED)
        self.NOT_FOUND = TestResponse("", status=status.HTTP_404_NOT_FOUND)
        self.TMR = TestResponse("", status=status.HTTP_429_TOO_MANY_REQUESTS)
        self.ERROR = TestResponse("",
                                  status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def test_parse_response(self):
        ggs = PeliasGeocoder(
            "test"
        )
        r = TestResponse(
            self.response,
            content_type="application/json",
            status=status.HTTP_200_OK
        )
        self.assertGreaterEqual(len(ggs._parse_response(r)), 1)
        self.assertRaises(GeocoderRequestError, ggs._parse_response,
                          self.BAD_REQUEST)
        self.assertRaises(GeocoderRequestError, ggs._parse_response,
                          self.UNAUTHORIZED)
        self.assertRaises(GeocoderRequestError, ggs._parse_response,
                          self.NOT_FOUND)
        self.assertRaises(GeocoderRequestError, ggs._parse_response,
                          self.TMR)
        self.assertRaises(GeocoderRequestError, ggs._parse_response,
                          self.ERROR)

    def test_parse_country(self):
        pgs = PeliasGeocoder(
            "test"
        )
        countries = pgs.parse_countries(self.response)
        self.assertEqual(len(countries), 1)
        self.assertEqual(countries[0], 'AU')

    def test_parse_addresses(self):
        pgs = PeliasGeocoder(
            "test"
        )
        addresses = pgs.parse_addresses(self.response)
        self.assertEqual(len(addresses), 1)
        self.assertEqual(addresses[0].postal_code, '2000')

    def test_serialize_addresses(self):
        pgs = PeliasGeocoder(
            "test"
        )
        addresses = pgs.parse_addresses(self.response)
        serialized_data = AddressSerializer(addresses, many=True).data
        self.assertEqual(serialized_data[0]['country']['alpha_2'], 'AU')
        self.assertEqual(serialized_data[0]['subdivision']['code'], 'AU-NSW')


class GoogleGeocoderTest(TestCase):

    def setUp(self):
        self.response = {
            "results": [
                {
                    "address_components": [
                        {
                            "long_name": "1600",
                            "short_name": "1600",
                            "types": ["street_number"]
                        },
                        {
                            "long_name": "Amphitheatre Pkwy",
                            "short_name": "Amphitheatre Pkwy",
                            "types": ["route"]
                        },
                        {
                            "long_name": "Mountain View",
                            "short_name": "Mountain View",
                            "types": ["locality", "political"]
                        },
                        {
                            "long_name": "Santa Clara County",
                            "short_name": "Santa Clara County",
                            "types": ["administrative_area_level_2",
                                      "political"]
                        },
                        {
                            "long_name": "California",
                            "short_name": "CA",
                            "types": ["administrative_area_level_1",
                                      "political"]
                        },
                        {
                            "long_name": "United States",
                            "short_name": "US",
                            "types": ["country", "political"]
                        },
                        {
                            "long_name": "94043",
                            "short_name": "94043",
                            "types": ["postal_code"]
                        }
                    ],
                    "formatted_address": "1600 Amphitheatre Parkway, Mountain View, CA 94043, USA",
                    "geometry": {
                        "location": {
                            "lat": 37.4224764,
                            "lng": -122.0842499
                        },
                        "location_type": "ROOFTOP",
                        "viewport": {
                            "northeast": {
                                "lat": 37.4238253802915,
                                "lng": -122.0829009197085
                            },
                            "southwest": {
                                "lat": 37.4211274197085,
                                "lng": -122.0855988802915
                            }
                        }
                    },
                    "place_id": "ChIJ2eUgeAK6j4ARbn5u_wAGqWA",
                    "plus_code": {
                        "compound_code": "CWC8+W5 Mountain View, California, United States",
                        "global_code": "849VCWC8+W5"
                    },
                    "types": ["street_address"]
                }
            ],
            "status": "OK"
        }

        self.ZERO_RESULTS = TestResponse({
            "results": [],
            "status": "ZERO_RESULTS"
        }, content_type="application/json")

        self.OVER_QUERY_LIMIT = TestResponse({
            "status": "OVER_QUERY_LIMIT"
        }, content_type="application/json")

        self.REQUEST_DENIED = TestResponse({
            "status": "REQUEST_DENIED"
        }, content_type="application/json")

        self.INVALID_REQUEST = TestResponse({
            "status": "INVALID_REQUEST"
        }, content_type="application/json")

        self.UNKNOWN_ERROR = TestResponse({
            "status": "UNKNOWN_ERROR"
        }, content_type="application/json")

    def test_parse_response(self):
        ggs = GoogleGeocoder(
            "test"
        )
        r = TestResponse(
            self.response,
            content_type="application/json",
            status=status.HTTP_200_OK)
        self.assertGreaterEqual(len(ggs._parse_response(r)['results']), 1)
        self.assertEqual(len(ggs._parse_response(self.ZERO_RESULTS)['results']),
                         0)
        self.assertRaises(GeocoderRequestError, ggs._parse_response,
                          self.OVER_QUERY_LIMIT)
        self.assertRaises(GeocoderRequestError, ggs._parse_response,
                          self.REQUEST_DENIED)
        self.assertRaises(GeocoderRequestError, ggs._parse_response,
                          self.INVALID_REQUEST)
        self.assertRaises(GeocoderRequestError, ggs._parse_response,
                          self.UNKNOWN_ERROR)

    def test_parse_country(self):
        ggs = GoogleGeocoder(
            "test"
        )
        countries = ggs.parse_countries(self.response)
        self.assertEqual(len(countries), 1)
        self.assertEqual(countries[0], 'US')

    def test_parse_addresses(self):
        ggs = GoogleGeocoder(
            "test"
        )
        addresses = ggs.parse_addresses(self.response)
        self.assertEqual(len(addresses), 1)
        self.assertEqual(addresses[0].postal_code, '94043')

    def test_serialize_addresses(self):
        ggs = GoogleGeocoder(
            "test"
        )
        addresses = ggs.parse_addresses(self.response)
        serialized_data = AddressSerializer(addresses, many=True).data
        self.assertEqual(serialized_data[0]['country']['alpha_2'], 'US')
        self.assertEqual(serialized_data[0]['subdivision']['code'], 'US-CA')


class GeocoderTestCase(TestCase):
    """
    Testing geocoders
    """

    def setUp(self) -> None:
        settings.GEOCODER_GOOGLE_KEY = os.environ.get('GOOGLE_API_KEY')
        settings.GEOCODER_PELIAS_KEY = os.environ.get('PELIAS_API_KEY')
        settings.PELIAS_GEOCODER_URL = PELIAS_TEST_URL

    def test_google(self) -> None:
        """
        Testing Google service
        """
        geocoder = service(service_type='geocoding',
                           service_name='google')
        self.assertEqual(geocoder.coder_type, 'google')

    def test_pelias(self):
        """
        Testing Pelias service
        """
        geocoder = service(service_type='geocoding',
                           service_name='pelias',
                           server_url=PELIAS_TEST_URL)
        self.assertEqual(geocoder.coder_type, 'pelias')

    def test_google_search(self):
        """
        Testing Google geocoding
        """
        if settings.GEOCODER_GOOGLE_KEY:
            geocoder = service(service_type='geocoding',
                               service_name='google')
            data = geocoder.search(
                address=TEST_ADDRESS,
                key=settings.GEOCODER_GOOGLE_KEY
            )
            self.assertIsNotNone(data)
        else:
            print("GEOCODER_GOOGLE_KEY not set, skipping test")

    def test_google_reverse(self):
        """
        Testing Google revrese geocoding
        """
        if settings.GEOCODER_GOOGLE_KEY:
            geocoder = service(service_type='geocoding',
                               service_name='google')
            data = geocoder.reverse(
                lat=TEST_LAT,
                lng=TEST_LNG,
                key=settings.GEOCODER_GOOGLE_KEY)
            self.assertIsNotNone(data)
        else:
            print("GEOCODER_GOOGLE_KEY not set, skipping test")

    def test_pelias_search(self):
        """
        Testing Pelias geocoding
        """
        if settings.GEOCODER_PELIAS_KEY:
            geocoder = service(service_type='geocoding',
                               service_name='pelias',
                               server_url=PELIAS_TEST_URL)
            data = geocoder.search(
                address=TEST_ADDRESS,
                key=settings.GEOCODER_PELIAS_KEY
            )
            self.assertIsNotNone(data)
        else:
            print("GEOCODER_PELIAS_KEY not set, skipping test")

    def test_pelias_reverse(self):
        """
        Testing Pelias reverse geocoding
        """
        if settings.GEOCODER_PELIAS_KEY:
            geocoder = service(service_type='geocoding',
                               service_name='pelias',
                               server_url=PELIAS_TEST_URL)
            data = geocoder.reverse(
                lat=TEST_LAT,
                lng=TEST_LNG,
                key=settings.GEOCODER_PELIAS_KEY
            )
            self.assertIsNotNone(data)
        else:
            print("GEOCODER_PELIAS_KEY not set, skipping test")

    def test_pelias_search_parse_countries(self):
        """
        Test with pelias search
        """
        if settings.GEOCODER_PELIAS_KEY:
            geocoder = service(service_type='geocoding',
                               service_name='pelias',
                               server_url=PELIAS_TEST_URL)
            data = geocoder.search(
                address=TEST_ADDRESS,
                key=settings.GEOCODER_PELIAS_KEY
            )
            self.assertIsNotNone(data)
            self.assertIn("FR", geocoder.parse_countries(data))
        else:
            print("GEOCODER_PELIAS_KEY not set, skipping test")

    def test_pelias_reverse_parse_countries(self):
        """
        Test with pelias reverse
        """
        if settings.GEOCODER_PELIAS_KEY:
            geocoder = service(service_type='geocoding',
                               service_name='pelias',
                               server_url=PELIAS_TEST_URL)
            data = geocoder.reverse(
                lat=TEST_LAT,
                lng=TEST_LNG,
                key=settings.GEOCODER_PELIAS_KEY
            )
            self.assertIsNotNone(data)
            if 'errors' in data:
                print("ERROR - Pelias service not available")
                return
            self.assertIn("FR", geocoder.parse_countries(data))
        else:
            print("GEOCODER_PELIAS_KEY not set, skipping test")

    def test_google_search_parse_countries(self):
        """
        Test with google search
        """
        if settings.GEOCODER_GOOGLE_KEY:
            geocoder = service(service_type='geocoding',
                               service_name='google')
            data = geocoder.search(
                address=TEST_ADDRESS,
                key=settings.GEOCODER_GOOGLE_KEY
            )
            self.assertIsNotNone(data)
            self.assertIn("FR", geocoder.parse_countries(data))
        else:
            print("GEOCODER_GOOGLE_KEY not set, skipping test")

    def test_google_reverse_parse_countries(self):
        """
        Test with google reverse
        """
        if settings.GEOCODER_GOOGLE_KEY:
            geocoder = service(service_type='geocoding',
                               service_name='google')
            data = geocoder.reverse(
                lat=TEST_LAT,
                lng=TEST_LNG,
                key=settings.GEOCODER_GOOGLE_KEY
            )
            self.assertIsNotNone(data)
            self.assertIn("FR", geocoder.parse_countries(data))
        else:
            print("GEOCODER_GOOGLE_KEY not set, skipping test")


class CountrySubdivisionTestCase(TestCase):

    def test_creation(self):
        sd = CountrySubdivision(code="FR-72")
        self.assertEqual(sd.name, "Sarthe")

    def test_invalid_code(self):
        self.assertRaises(
            CountrySubdivisionNotFound,
            CountrySubdivision,
            code="not there")

    def test_list_for_country(self):
        sd = CountrySubdivision.list_for_country(country_code="FR")
        self.assertEqual(len(sd), 125)

    def test_list_for_wrong_country(self):
        self.assertRaises(
            CountrySubdivisionNotFound,
            CountrySubdivision.list_for_country,
            country_code="who is this ?"
        )

    def test_search(self):
        sd = CountrySubdivision.search(search_term="toto")
        self.assertEqual(len(sd), 1)  # 'Totonicapán'
        sd = CountrySubdivision.search(search_term="toto is not there")
        self.assertEqual(len(sd), 0)  # 'Totonicapán'

    def test_list_country_ordering(self):
        sd_name = CountrySubdivision.list_for_country(
            country_code="US",
            ordering='name')
        sd_code = CountrySubdivision.list_for_country(
            country_code="US",
            ordering='code')
        sd_type = CountrySubdivision.list_for_country(
            country_code="FR",
            ordering='type')
        self.assertEqual(sd_name[0].name, 'Alabama')
        self.assertEqual(sd_name[-1].name, 'Wyoming')
        self.assertEqual(sd_code[0].name, 'Alaska')
        self.assertEqual(sd_code[-1].name, 'Wyoming')
        self.assertEqual(sd_type[0].type, 'Dependency')
        self.assertEqual(sd_type[-1].type, 'Overseas territorial collectivity')

    def test_parent(self):
        sd = CountrySubdivision(code='FR-72')
        self.assertEqual(sd.parent_code, 'FR-PDL')
        self.assertEqual(sd.parent.name, 'Pays-de-la-Loire')
        sd = CountrySubdivision(code='US-WY')
        self.assertIsNone(sd.parent)

    def test_children(self):
        sd = CountrySubdivision(code='FR-72')
        self.assertEqual(len(sd.parent.children()), 5)
        self.assertEqual(type(sd.parent.children()[0]), CountrySubdivision)
        self.assertEqual(len(sd.parent.children(search_term="FR-72")), 1)


class CountrySubdivisionAPITestCase(TestCase):

    def test_list_request(self):
        """
        Testing the list of country subdivisions
        """
        client = APIClient()
        response = client.get('/countries/FR/subdivisions/', format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data),
                         len(CountrySubdivision.list_for_country(
                             country_code='FR')))
        self.assertEqual(response.data[0].get('name'), 'Ain')

    def test_list_sorted_code_request(self):
        """
        testing code ordering on List API
        """
        client = APIClient()
        response = client.get(
            '/countries/FR/subdivisions/',
            data={'ordering': 'code'},
            format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            len(response.data),
            len(CountrySubdivision.list_for_country(country_code='FR')))
        self.assertEqual(response.data[0].get('name'), 'Ain')

    def test_retrieve_request(self):
        """
        Testing retrieve on country subdivision
        """
        client = APIClient()
        response = client.get(
            '/countries/US/subdivisions/US-OK/',
            format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        csd = CountrySubdivisionSerializer(data=response.json())
        self.assertTrue(csd.is_valid())
        sd = csd.create(csd.validated_data)
        self.assertEqual(sd.name, 'Oklahoma')
        self.assertEqual(sd.code, 'US-OK')
        self.assertEqual(sd.type, 'State')
        self.assertEqual(sd.country_code, 'US')

    def test_retrieve_parent(self):
        """
        Testing retrieve country subdivision parent
        """
        client = APIClient()
        response = client.get('/countries/FR/subdivisions/FR-72/parent/',
                              format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        csd = CountrySubdivisionSerializer(data=response.json())
        self.assertTrue(csd.is_valid())
        sd = csd.create(csd.validated_data)
        self.assertEqual(sd.name, 'Pays-de-la-Loire')

    def test_retrieve_children(self):
        """
        Testing retrieve on country subdivision children
        """
        client = APIClient()
        response = client.get(
            '/countries/FR/subdivisions/FR-PDL/children/',
            format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        csd = CountrySubdivisionSerializer(data=response.json(), many=True)
        self.assertTrue(csd.is_valid())
        self.assertEqual(len(response.json()), 5)

    def test_retrieve_children_search(self):
        """
        Testing retrieve on country subdivision children
        """
        client = APIClient()
        response = client.get(
            '/countries/FR/subdivisions/FR-PDL/children/',
            data={'search': 'FR-72'},
            format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        csd = CountrySubdivisionSerializer(data=response.json(), many=True)
        self.assertTrue(csd.is_valid())
        self.assertEqual(len(response.json()), 1)
