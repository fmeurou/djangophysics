"""
GraphQL test module
"""
import datetime
from json import dumps, loads
from django.test import TestCase
from rest_framework.test import APIClient
from djangophysics.countries.models import Country
from djangophysics.currencies.models import Currency
from djangophysics.rates.models import Rate

class GraphQLTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        pass

    def test_countries(self):
        """
        Test list of countries
        """
        gql = {
            'query': "{countries {alpha_2, name}}"
        }
        response = self.client.post(
            '/graphql',
            data=gql,
            format='json')
        self.assertIsNone(response.json().get('errors'))
        self.assertIsNotNone(response.json().get('data'))
        self.assertEqual(len(response.json()['data']['countries']),
                         len(Country.all_countries()))

    def test_search_countries(self):
        """
        Test list of countries with filter
        """
        gql = {
            'query': """{countries(term:"france") {alpha_2, name}}"""
        }
        response = self.client.post(
            '/graphql',
            data=gql,
            format='json')
        self.assertIsNone(response.json().get('errors'))
        self.assertIsNotNone(response.json().get('data'))
        self.assertEqual(len(response.json()['data']['countries']),
                         len(Country.search(term="france")))

    def test_search_countries_bad_param(self):
        """
        Test list of countries with filter
        """
        gql = {
            'query': """{countries(trem:"france") {alpha_2, name}}"""
        }
        response = self.client.post(
            '/graphql',
            data=gql,
            format='json')
        self.assertIsNotNone(response.json().get('errors'))

    def test_country(self):
        """
        Test country details
        """
        gql = {
            'query': """{country(alpha_2:"fr") {alpha_2, name}}"""
        }
        response = self.client.post(
            '/graphql',
            data=gql,
            format='json')
        self.assertIsNone(response.json().get('errors'))
        self.assertIsNotNone(response.json().get('data'))
        self.assertIn('country', response.json()['data'])
        self.assertNotIn("alpha_3", response.json()['data']['country'])

    def test_country_currencies(self):
        """
        Test currencies of a country
        """
        gql = {
            'query': """{country(alpha_2:"fr") {
            alpha_2, name, currencies {code}}}"""
        }
        response = self.client.post(
            '/graphql',
            data=gql,
            format='json')
        resp = response.json()
        self.assertIsNone(resp.get('errors'))
        self.assertIsNotNone(resp.get('data'))
        self.assertIn('country', resp['data'])
        self.assertIn("currencies", resp['data']['country'])
        self.assertEqual(resp['data']['country']['currencies'][0]['code'],
                         "EUR")

    def test_country_unit_system_obj(self):
        """
        Test currencies of a country
        """
        gql = {
            'query': """{country(alpha_2:"fr") 
            {
              alpha_2, 
              name, 
              currencies {code}
              unit_system_obj   {
                system_name
              }
            }
            }"""
        }
        response = self.client.post(
            '/graphql',
            data=gql,
            format='json')
        resp = response.json()
        self.assertIsNone(resp.get('errors'))
        self.assertIsNotNone(resp.get('data'))
        self.assertIn('country', resp['data'])
        self.assertIn("currencies", resp['data']['country'])
        self.assertEqual(
            resp['data']['country']['unit_system_obj']['system_name'], "SI")

    def test_currencies(self):
        """
        Test list of currencies
        """
        gql = {
            'query': "{currencies {code, currency_name}}"
        }
        response = self.client.post(
            '/graphql',
            data=gql,
            format='json')
        self.assertIsNone(response.json().get('errors'))
        self.assertIsNotNone(response.json().get('data'))
        self.assertEqual(len(response.json()['data']['currencies']),
                         len(Currency.all_currencies()))

    def test_search_currencies(self):
        """
        Test list of currencies with filter
        """
        gql = {
            'query': """{currencies(term:"eur") {code, currency_name}}"""
        }
        response = self.client.post(
            '/graphql',
            data=gql,
            format='json')
        self.assertIsNone(response.json().get('errors'))
        self.assertIsNotNone(response.json().get('data'))
        self.assertEqual(len(response.json()['data']['currencies']),
                         len(Currency.search(term="EUR")))

    def test_search_currencies_bad_param(self):
        """
        Test list of currencies with filter
        """
        gql = {
            'query': """{currencies(trem:"eur") {code, currency_name}}"""
        }
        response = self.client.post(
            '/graphql',
            data=gql,
            format='json')
        self.assertIsNotNone(response.json().get('errors'))

    def test_currency(self):
        """
        Test currency details
        """
        gql = {
            'query': """{currency(code:"eur") {code, currency_name}}"""
        }
        response = self.client.post(
            '/graphql',
            data=gql,
            format='json')
        self.assertIsNone(response.json().get('errors'))
        self.assertIsNotNone(response.json().get('data'))
        self.assertIn('currency', response.json()['data'])
        self.assertNotIn("alpha_3", response.json()['data']['currency'])

    def test_currency_countries(self):
        """
        Test list of countries of a currency
        """
        gql = {
            'query': """
            {currency(code:"eur") {
                code, name, countries {alpha_2}}}"""
        }
        response = self.client.post(
            '/graphql',
            data=gql,
            format='json')
        resp = response.json()
        self.assertIsNone(resp.get('errors'))
        self.assertIsNotNone(resp.get('data'))
        self.assertIn('currency', resp['data'])
        self.assertIn("countries", resp['data']['currency'])
        self.assertEqual(resp['data']['currency']['countries'][0]['alpha_2'],
                         "GP")

    def test_currency_rates(self):
        """
        Test Currency rates_to and rates_from functions
        """
        d = datetime.date.today().strftime('%Y-%m-%d')
        Rate.objects.fetch_rates(
            currency="EUR",
            base_currency="USD"
        )
        Rate.objects.fetch_rates(
            currency="USD",
            base_currency="EUR"
        )
        gql = {
            'query': """
            |
              currency(code:"EUR") |
              code,
              rate_from(currency:"USD", value_date:"{d}") |
                currency,
                base_currency,
                value
              ||,
              rate_to(currency:"USD", value_date:"{d}") |
                currency,
                base_currency,
                value
              ||
            ||
            ||
            """.format(d=d).replace('||', '}').replace('|', '{')
        }
        response = self.client.post(
            '/graphql',
            data=gql,
            format='json')
        resp = response.json()
        self.assertIsNone(resp.get('errors'))
        self.assertIsNotNone(resp.get('data'))
        self.assertIn('currency', resp['data'])
        self.assertEqual(resp['data']['currency']['code'], "EUR")
        self.assertEqual(
            resp['data']['currency']['rate_to']['currency'],
            "USD")
        self.assertEqual(
            resp['data']['currency']['rate_from']['base_currency'],
            "USD")
