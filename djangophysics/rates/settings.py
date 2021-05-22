"""
Rates module settings
"""

import os

BASE_CURRENCY = 'EUR'
RATE_SERVICE = 'ecb'
CURRENCYLAYER_API_KEY = os.environ.get('CURRENCYLAYER_API_KEY')
FOREX_API_KEY = os.environ.get('FOREX_API_KEY')