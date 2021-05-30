"""
ECB Open Data service
"""
import io
import logging
import os
import zipfile
from datetime import date as dt
from datetime import datetime, timedelta
from typing import Iterator

import requests
from django.conf import settings

from . import RateService, RatesNotAvailableError

SOURCE_TYPES = {
    'latest': {
        'url': "https://www.ecb.europa.eu/stats/eurofxref/eurofxref.zip",
        'filename': 'eurofxref.csv'
    },
    'historical': {
        'url': "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip",
        'filename': 'eurofxref-hist.csv'
    }
}


class ECBService(RateService):
    _available_currencies = None
    _rates_cache = None
    _instance = None

    def __init__(self):
        self._rates_cache = {}
        self._available_currencies = []

    def _extract_currencies(self, rates_grid):
        self._available_currencies = rates_grid[0][1:]

    def _extract_rates(self, rates_grid):
        dates = []
        for line in rates_grid[1:]:
            try:
                d = datetime.strptime(line[0], '%d %B %Y').date()
            except ValueError:
                try:
                    d = datetime.strptime(line[0], '%Y-%m-%d').date()
                except ValueError as e:
                    raise RatesNotAvailableError(str(e)) from e
            self._rates_cache[d] = {}
            dates.append(d)
            for i, cell in enumerate(line[1:]):
                try:
                    self._rates_cache[d][
                        rates_grid[0][i + 1].strip()] = float(cell)
                except ValueError:
                    pass
        # Fill the blanks (week ends?)
        sorted_dates = sorted(dates)
        first_date = sorted_dates[0]
        last_date = dt.today()
        last_rates = self._rates_cache[first_date]
        for i in range((last_date-first_date).days + 1):
            d = (first_date + timedelta(i))
            if d in self._rates_cache:
                last_rates = self._rates_cache[d]
            else:
                self._rates_cache[d] = last_rates

    def _fetch_rates(self, source_type):
        """
        Fetch rates from ECB rates statistics page
        """
        source = SOURCE_TYPES[source_type]
        response = requests.get(source['url'])
        if response.status_code == 200:
            try:
                z = zipfile.ZipFile(io.BytesIO(response.content))
                z.extract(
                    source['filename'],
                    path=getattr(settings, 'TMP_DIR', '/tmp'))
            except zipfile.BadZipfile as e:
                raise RatesNotAvailableError("Incorrect source response")
        else:
            raise RatesNotAvailableError(response.text)

    def _read_rates(self, source_type):
        """
        Read rates from temporary file
        """
        filepath = os.path.join(
            getattr(settings, 'TMP_DIR', '/tmp'),
            SOURCE_TYPES[source_type]['filename']
        )
        now = datetime.now()
        if not os.path.exists(filepath) or \
                (now - datetime.fromtimestamp(
                    os.stat(path=filepath).st_mtime)).days >= 1:
            self._fetch_rates(source_type=source_type)
        try:
            with open(filepath) as source_file:
                content = source_file.read()
            rates_grid = [l.split(',')[:-1] for l in
                          content.split('\n')][:-1]
            self._extract_currencies(rates_grid=rates_grid)
            self._extract_rates(rates_grid=rates_grid)
        except (IOError, IndexError, ValueError, TypeError) as e:
            raise RatesNotAvailableError(str(e)) from e

    def available_currencies(self) -> Iterator:
        """
        List availbale currencies for the service
        """
        return self._available_currencies

    def _get_from_range(self, start_date, end_date):
        filtered_rates = {}
        dates = [(start_date + timedelta(i))
                 for i in range((end_date - start_date).days + 1)]
        for d in dates:
            try:
                filtered_rates[d] = self._rates_cache[d]
            except KeyError:
                logging.warning(f"No rate for this date {d}")
                pass
        return filtered_rates

    def _get_rate(self, rate_date: dict,
                  base_currency: str,
                  currency: str) -> float:
        """
        Get conversion rate between base currency and currency
        :param rate_date: list of rates at a given date
        """
        try:
            denum = 1 if base_currency == 'EUR' else rate_date[base_currency]
            num = 1 if currency == 'EUR' else rate_date[currency]
        except KeyError as e:
            raise RatesNotAvailableError(str(e)) from e
        if denum:
            return num / denum
        else:
            raise RatesNotAvailableError()

    def _fetch_single(self, base_currency: str, currency: str,
                      date_obj: dt, to_obj: dt = None):
        rates_grid = {}
        if to_obj:
            rates_grid = self._get_from_range(
                start_date=date_obj,
                end_date=to_obj)
        elif date_obj in self._rates_cache:
            rates_grid[date_obj] = self._rates_cache[date_obj]
        output = []
        for d, date_rates in rates_grid.items():
            try:
                output.append(
                    {
                        'base_currency': base_currency.strip(),
                        'currency': currency.strip(),
                        'date': d,
                        'value': self._get_rate(
                            rate_date=date_rates,
                            base_currency=base_currency,
                            currency=currency
                        )
                    }
                )
            except RatesNotAvailableError as e:
                logging.warning(f"Rate not {base_currency} -> {currency} "
                                f"not available at date {d}")
        return output

    def _fetch_all(self, base_currency: str,
                   date_obj: dt, to_obj: dt = None):
        output = []
        for currency in self._available_currencies:
            output.extend(self._fetch_single(
                base_currency=base_currency.strip(),
                currency=currency.strip(),
                date_obj=date_obj,
                to_obj=to_obj
            ))
        return output

    def fetch_rates(self,
                    base_currency: str = settings.BASE_CURRENCY,
                    currency: str = None,
                    date_obj: dt = dt.today(),
                    to_obj: dt = None) -> []:
        if date_obj == dt.today():
            self._read_rates('latest')
        else:
            self._read_rates('historical')
        if currency:
            return self._fetch_single(
                base_currency=base_currency,
                currency=currency,
                date_obj=date_obj,
                to_obj=to_obj
            )
        else:
            return self._fetch_all(
                base_currency=base_currency,
                date_obj=date_obj,
                to_obj=to_obj
            )
