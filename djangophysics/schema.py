from ariadne import QueryType, gql, make_executable_schema, ObjectType

from ariadne import QueryType, gql, make_executable_schema, ObjectType

from .countries.models import Country
from .currencies.models import Currency
from .rates.models import Rate
from .units.models import UnitSystem, Dimension, Unit

type_defs = '''
    """
    Country GraphQL services
    """
    
    type User   {
        username: String!,
        email: String,
        is_authenticated: Int!
    }
    
    type Currency   {
        code: String!,
        name: String!,
        currency_name: String!,
        exponent: Int,
        number: Int!,
        value: String,
        symbol: String,
        countries: [Country],
        rates_to(currency: String!, value_date: String!): [Rate]
        rates_from(currency: String!, value_date: String!): [Rate]            
    }
    
    type TimeZone   {
        name: String!,
        offset: String!,
        numeric_offset: Int!,
        current_time: String!
    }
    
    type Country {
        name: String!,
        numeric: Int!,
        alpha_2: String!,
        alpha_3: String!,
        region: String,
        subregion: String,
        tld: String, 
        capital: String,
        population: Int,
        colors: [String], 
        timezones: [TimeZone],
        currencies: [Currency]
    }
    
    type Rate   {
        currency: String!,
        currency_obj: Currency,
        base_currency: String!,
        base_currency_obl: Currency,
        value_date: String!,
        value: Float!
    }
    
    type RatesPage   {
        items: [Rate]
        next: Int,
        previous: Int
    }
    
    type UnitSystem {
        system_name: String,
        available_dimensions: [Dimension]
    }
    
    type Dimension  {
        code: String!,
        name: String!,
        unit_system: UnitSystem!,
        units: [Unit],
        base_unit: Unit
    }
    
    type Unit   {
        code: String,
        name: String,
        symbol: String,
        dimensions: [Dimension],
        unit_system: UnitSystem!
    }
    
    type Query {
        "Return queries"
        user: User
        countries(term: String): [Country]
        country(alpha_2: String!): Country
        currencies(term: String): [Currency]
        currency(code: String!): Currency
        rates(base_currency: String, currency: String, value_date: String, page: Int, page_size: Int): RatesPage
        rate(base_currency: String!, currency: String!, value_date: String!): Rate
        unit_systems: [UnitSystem],
        unit_system(name: String!): UnitSystem,
        dimensions(system_name: String!): [Dimension],
        dimension(system_name: String!, code: String!): Dimension,
        units(system_name: String!): [Unit]
        unit(system_name: String!, unit_name: String!): Unit 
    }
    
'''

gql(type_defs)

query = QueryType()


@query.field("user")
def resolve_user(_, info):
    request = info.context.get('request', None)
    print(dir(request))
    if request:
        return request.user


# Root resolver
@query.field("countries")
def resolve_countries(_, info, term=''):
    return Country.search(term=term)


@query.field("country")
def resolve_country(_, info, alpha_2=''):
    return Country(alpha_2)


@query.field("currencies")
def resolve_currencies(_, info, term=''):
    return Currency.search(term=term)


@query.field("currency")
def resolve_currency(_, info, code=''):
    return Currency(code=code)


@query.field("rate")
def resolve_rate(_, info,
                 base_currency='EUR',
                 currency='USD',
                 value_date=None):
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


schema = make_executable_schema(type_defs, query)
