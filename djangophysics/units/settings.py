"""
Settings for Units module
"""
from django.utils.translation import gettext_lazy as _

# This will display these units in the list of units
ADDITIONAL_DIMENSIONS = {
    '[massic_heating_value]': {
        'name': _('massic heating value'),
        'relation': '[energy]/[mass]'
    },
    '[volumic_heating_value]': {
        'name': _('volumic heating value'),
        'relation': '[energy]/[volume]'
    },
}

# This will display these units in the list of units
ADDITIONAL_UNITS = {}

# Show units with prefixed values in APIs
PREFIXED_UNITS_DISPLAY = {
    'meter': ['milli', 'centi', 'kilo'],
    'gram': ['milli', 'kilo'],
    'second': ['micro', 'milli'],
    'ampere': ['milli'],
}
