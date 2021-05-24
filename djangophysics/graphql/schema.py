"""
Djangophysics GraphQL schemas
"""
from ariadne import QueryType, gql, make_executable_schema

from ..core.helpers import validate_language, service
from ..countries.models import Country, CountrySubdivision
from ..currencies.models import Currency
from ..rates.models import Rate
from ..units.models import UnitSystem, Dimension

# GraphQL Schema first
type_defs = '''
    
    """
    User GraphQL services,
    """
    type User   {
        username: String!,
        email: String,
        is_authenticated: Int!
    }
    
    """
    Currency GraphQL services
    """
    type Currency   {
        "ISO4217 code"
        code: String!,
        "ISO4217 name"
        name: String!,
        "Human readable name"
        currency_name: String!,
        "ISO4217 exponent"
        exponent: Int,
        "ISO4217 number"
        number: Int!,
        "ISO4217 value"
        value: String,
        "Symbol of the currency"
        symbol: String,
        "Countries using this currency"
        countries: [Country],
        "Convert to another currency"
        rate_to(currency: String!, value_date: String!): Rate
        "Convert from another currency"
        rate_from(currency: String!, value_date: String!): Rate            
    }
    
    """
    Timezone object, obtained from Country
    """
    type TimeZone   {
        "Name of the timezone"
        name: String!,
        "UTC offset"
        offset: String!,
        "UTC offset numeric value"
        numeric_offset: Int!,
        "Current time"
        current_time: String!
    }
    
    """
    GPS Location
    """
    type Location    {
        "Latitude"
        lat: Float!,
        "Longitude"
        lng: Float!
    }
    
    """
    Address  
    """
    type Address {
        "GPS coordinates"
        location: Location,
        "Street number"
        street_number: String,
        "Street name"
        street: String,
        "Postal code"
        postal_code: String,
        "Locality or city name"
        locality: String
        "County or administrative level"
        county: CountrySubdivision,
        "County or administrative level name"
        county_label: String,
        "Subdivision name"
        subdivision_label: String,
        "Subdivision object"
        subdivision: CountrySubdivision,
        "Country object"
        country: Country
        "Result confidence, not always available"
        confidence: Int,
    }
    
    """
    List of countries based on the ISO-3166
    """
    type Country {
        "ISO 3166 Name of the country"
        name: String!,
        "ISO 3166 numeric value"
        numeric: Int!,
        "ISO 3166 alpha2 code"
        alpha_2: String!,
        "ISO 3166 alpha3 trigram"
        alpha_3: String!,
        "Name of the region the country belongs to"
        region: String,
        "Name of the subregion the country belongs to"
        subregion: String,
        "TLD associated with the country"
        tld: [String], 
        "Capital city"
        capital: String,
        "Population of the country"
        population: Int,
        "Country subdivisions"
        subdivisions: [CountrySubdivision],
        "List of colors of the flag"
        colors: [String], 
        "List of timezones of the country"
        timezones: [TimeZone],
        "List of the currencies used in the country"
        currencies: [Currency],
        "Official unit system name of the country"
        unit_system: String,
        "Unt system object"
        unit_system_obj: UnitSystem
    }
    
    type CountrySubdivision {
        "ISO 3166-2 Name of the subdivision"
        name: String!,
        "ISO 3166-2 Code of the subdivision"
        code: String!,
        "Subdivision type"
        type: String,
        "ISO 3166 Contry alpha_2"
        country_code: String!,
        "Country of the subdivision"
        country: Country!,
        "Subdivision parent code"
        parent_code: String,
        "Subdivision parent"
        parent: CountrySubdivision,
        "Subdivision children"
        children: [CountrySubdivision]
    }
        
    """
    Conversion rate between two currencies
    """
    type Rate   {
        "Currency ISO 4217 code to convert to"
        currency: String!,
        "Currency object to convert to"
        currency_obj: Currency,
        "Currency ISO4217 to convert from"
        base_currency: String!,
        "Currency object to convert from"
        base_currency_obl: Currency,
        "Date of value"
        value_date: String!,
        "Value of the conversion rate"
        value: Float!
    }
    
    """
    Paginated List of rates
    """
    type RatesPage   {
        "List of rates"
        items: [Rate]
        "Number of the next page"
        next: Int,
        "Number of the previous page"
        previous: Int
    }
    
    """
    Unit system
    """
    type UnitSystem {
        "Name of the dimension"
        system_name: String,
        "Dimensions available under this unit system"
        available_dimensions(search_term: String, ordering: String): [Dimension]
    }
    
    """
    Physical dimension
    """    
    type Dimension  {
        "Technical name of the dimension, in sqaure brackets [length]"
        code: String!,
        "Human readable name of the dimension"
        name: String!,
        "Unit system of the dimension"
        unit_system: UnitSystem!,
        "List of units of the dimension"
        units: [Unit],
        "Reference unit of the dimension"
        base_unit: Unit
    }
    
    """
    Physical units
    """
    type Unit   {
        "Technical name of the unit"
        code: String!,
        "Human readable name"
        name: String!,
        "Unit symbol"
        symbol: String,
        "List of physical dimensions associated with the unit"
        dimensions: [Dimension],
        "Unit system of the unit"
        unit_system: UnitSystem!
    }
    
    """
    Root Query
    """
    type Query {
        "Current user resolver"
        user: User
        "Searchable list of countries"
        countries(term: String): [Country]
        "Country details"
        country(alpha_2: String!): Country
        "Geocode interface: key is the API key to the geocoding service"
        geocode(address: String!, key: String, language: String, geocoder: String): [Address]
        "Reverse Geocode interface: key is the API key to the geocoding service"
        reverse_geocode(atitude: Float!, longitude: Float!, key: String, language: String, geocoder: String): [Address]
        "Searchable list of subdivisions for a country"
        country_subdivisions_search(search_term: String!, country_code: String, ordering: String): [CountrySubdivision]
        "List of subdivisions for a country"
        country_subdivisions(alpha_2: String!): [CountrySubdivision]
        "Country subdivision details"
        country_subdivision(alpha_2: String!, code: String!): CountrySubdivision
        "Searchable list of currencies"
        currencies(term: String): [Currency]
        "Currency details"
        currency(code: String!): Currency
        "List of rates filterable by base currency, currency or date"
        rates(base_currency: String, currency: String, value_date: String, page: Int, page_size: Int): RatesPage
        "Details of a conversion rate"
        rate(base_currency: String!, currency: String!, value_date: String!): Rate
        "List of available unit systems"
        unit_systems: [UnitSystem],
        "Details of a unit system"
        unit_system(name: String!): UnitSystem,
        "List of dimensions for a unit system"
        dimensions(system_name: String!): [Dimension],
        "Details of a dimension from unit system and dimension code"
        dimension(system_name: String!, code: String!): Dimension,
        "List of units for a unit system"
        units(system_name: String!): [Unit]
        "Details of a unit"
        unit(system_name: String!, unit_name: String!): Unit 
    }
    
'''

gql(type_defs)

# Root resolver
query = QueryType()


# User resolver
@query.field("user")
def resolve_user(_, info):
    """
    User resolver, if user is connected
    :param _: all params
    :param info: QraphQL request context
    """
    request = info.context.get('request', None)
    if request:
        return request.user


# Countries resolver
@query.field("countries")
def resolve_countries(_, info, term=''):
    """
    Country resolver
    :param info: QraphQL request context
    :param term: search countries containing term
    """
    return Country.search(term=term)


@query.field("country")
def resolve_country(_, info, alpha_2):
    """
    Country resolver
    :param info: QraphQL request context
    :param alpha_2: ISO3166 alpha2 code
    """
    return Country(alpha_2)


@query.field("country_subdivisions")
def resolve_country_subdivisions(_, info, alpha_2):
    """
    Country resolver
    :param info: QraphQL request context
    :param alpha_2: ISO 3166 alpha2 code
    :param code: ISO 3166-2 code
    """
    return CountrySubdivision.list_for_country(country_code=alpha_2)


@query.field("country_subdivisions_search")
def resolve_country_subdivision_search(
        _, info,
        search_term: str,
        country_code: str = None,
        ordering: str = 'name'):
    """
    Country resolver
    :param info: QraphQL request context
    :param search term: search for a term in name, code and type
    :param country_code: ISO 3166 code
    :param ordering: order on field name, code or type
    """
    return CountrySubdivision.search(
        search_term=search_term,
        country_code=country_code,
        ordering=ordering
    )


@query.field("country_subdivision")
def resolve_country_subdivision(_, info, alpha_2, code):
    """
    Country resolver
    :param info: QraphQL request context
    :param alpha_2: ISO 3166 alpha2 code
    :param code: ISO 3166-2 code
    """
    return CountrySubdivision(code=code)


@query.field("currencies")
def resolve_currencies(_, info, term=''):
    """
    Currencies resolver
    :param info: QraphQL request context
    :param term: search currencies containing term
    """
    return Currency.search(term=term)


@query.field("currency")
def resolve_currency(_, info, code=''):
    """
    Country resolver
    :param info: QraphQL request context
    :param code: ISO4217 code
    """
    return Currency(code=code)


@query.field("rate")
def resolve_rate(_, info,
                 base_currency='EUR',
                 currency='USD',
                 value_date=None):
    """
    Rate resolver, doesn't take CustomRates into account
    :param info: QraphQL request context
    :param base_currency: base currency ISO4217 code
    :param currency: currency  ISO4217 code
    :param value_date: date of value for the rate "YYYY-MM-DD"
    """
    rate = Rate.objects.find_rate(
        base_currency=base_currency.upper(),
        currency=currency.upper(),
        date_obj=value_date
    )
    return rate


@query.field("rates")
def resolve_rates_page(_, info,
                       base_currency=None,
                       currency=None,
                       value_date=None,
                       page=0,
                       page_size=10):
    """
    Paginated list of rates, doesn't take CustomRates into account
    :param info: QraphQL request context
    :param base_currency: base currency ISO4217 code
    :param currency: currency  ISO4217 code
    :param value_date: date of value for the rate "YYYY-MM-DD",
    :param page: page number
    :param page_size: number of elements in a page
    """
    rates = Rate.objects.filter(
        user__isnull=True,
        key__isnull=True,
    )
    if currency:
        rates = rates.filter(currency=currency)
    if base_currency:
        rates = rates.filter(base_currency=base_currency)
    if value_date:
        rates = rates.filter(value_date=value_date)
    cnt = rates.count()
    rates = rates[page * page_size: (page + 1) * page_size]
    return {
        'previous': page - 1 if page else 0,
        'next': page + 1 if page < (cnt / page_size) else page,
        'items': rates
    }


@query.field("unit_systems")
def resolve_unit_systems(_, info):
    return [UnitSystem(system_name=us) for us in UnitSystem.available_systems()]


@query.field("unit_system")
def resolve_unit_system(_, info, name):
    return UnitSystem(system_name=name)


@query.field("dimensions")
def resolve_dimensions(_, info, system_name):
    return UnitSystem(system_name=system_name).available_dimensions()


@query.field("dimension")
def resolve_dimension(_, info, system_name, code):
    us = UnitSystem(system_name=system_name)
    return Dimension(unit_system=us, code=code)


@query.field("units")
def resolve_dimensions(_, info, system_name):
    us = UnitSystem(system_name=system_name)
    return [us.unit(name) for name in us.available_unit_names()]


@query.field("dimension")
def resolve_dimension(_, info, system_name, unit_name):
    us = UnitSystem(system_name=system_name)
    return us.unit(unit_name=unit_name)


@query.field("geocode")
def resolve_geocode(_, info, address: str, key: str,
                    language: str = 'en', geocoder: str = 'google'):
    language = validate_language(lang=language)
    geocoder = service(
        service_type='geocoding',
        service_name=geocoder
    )
    data = geocoder.search(
        address=address,
        key=key,
        language=language
    )
    return geocoder.addresses(data)


@query.field("reverse_geocode")
def resolve_reverse_geocode(_, info, latitude: float, longitude: float, key: str,
                    language: str = 'en', geocoder: str = 'google'):
    language = validate_language(lang=language)
    geocoder = service(
        service_type='geocoding',
        service_name=geocoder
    )
    data = geocoder.reverse(
        lat=latitude,
        lng=longitude,
        key=key,
        language=language
    )
    return geocoder.addresses(data)


schema = make_executable_schema(type_defs, query)
