"""
Units models
"""
import logging
import re
from datetime import date

import pint.systems
from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import ugettext as _

from djangophysics.converters.models import BaseConverter, ConverterResult, \
    ConverterResultDetail, ConverterResultError, ConverterLoadError
from djangophysics.countries.models import Country
from . import UNIT_EXTENDED_DEFINITION, DIMENSIONS, \
    UNIT_SYSTEM_BASE_AND_DERIVED_UNITS, \
    ADDITIONAL_BASE_UNITS, PREFIX_SYMBOL
from .exceptions import UnitConverterInitError, DimensionNotFound, \
    UnitSystemNotFound, UnitNotFound, \
    UnitDuplicateError, UnitDimensionError, \
    UnitValueError, DimensionValueError, DimensionDimensionError, \
    DimensionDuplicateError
from .settings import ADDITIONAL_UNITS, ADDITIONAL_DIMENSIONS, \
    PREFIXED_UNITS_DISPLAY


class Quantity:
    """
    Quantity class
    """
    system = None
    unit = None
    value = 0
    date_obj = None

    def __init__(self, system: str, unit: str,
                 value: float, date_obj: date = None):
        """
        Initialize quantity on unit system
        """
        self.system = system
        self.unit = unit
        self.value = value
        self.date_obj = date_obj

    def __repr__(self):
        """
        Look beautiful
        """
        return f'{self.value} {self.unit} ({self.system})'


class Unit:
    """
    Unit mock for hinting
    """
    pass


class UnitSystem:
    """
    Pint UnitRegistry wrapper
    """
    ureg = None
    system_name = None
    system = None
    _additional_units = set()
    dimensions_cache = {}
    units_cache = {}
    user = None
    key = None
    _additional_dimensions = set()

    def __init__(self, system_name: str = 'SI',
                 fmt_locale: str = 'en', user: User = None,
                 key: str = None):
        """
        Initialize UnitSystem from name and user / key
        information for loading custom units
        """
        found = False
        for available_system in UnitSystem.available_systems():
            if system_name.lower() == available_system.lower():
                system_name = available_system
                found = True
        if not found:
            raise UnitSystemNotFound("Invalid unit system")
        self.system_name = system_name
        try:
            additional_dimensions_settings = settings.PHYSICS_ADDITIONAL_DIMENSIONS
        except AttributeError:
            additional_dimensions_settings = ADDITIONAL_DIMENSIONS
        try:
            additional_units_settings = settings.PHYSICS_ADDITIONAL_UNITS
        except AttributeError:
            additional_units_settings = ADDITIONAL_UNITS
        self.user = user
        self.key = key
        try:
            self.ureg = pint.UnitRegistry(
                system=system_name,
                fmt_locale=fmt_locale)
            self.system = getattr(self.ureg.sys, system_name)
            self._load_additional_dimensions(
                dimensions=additional_dimensions_settings)
            self._load_additional_units(units=ADDITIONAL_BASE_UNITS)
            self._load_additional_units(units=additional_units_settings)
            if user:
                self._load_custom_dimensions(user=user, key=key)
                self._load_custom_units(user=user, key=key)
            self._rebuild_cache()
        except (FileNotFoundError, AttributeError) as e:
            raise UnitSystemNotFound(f"Invalid unit system: {str(e)}")

    def _rebuild_cache(self):
        """
        Rebuild registry cache
        It should be in the define method of the registry
        """
        self.ureg._build_cache()
        self.dimensions_cache = self.available_dimensions()
        self.units_cache = self.available_units()

    def _load_additional_dimensions(
            self, dimensions: dict,
            redefine: bool = False) -> bool:
        """
        Load additional base units in registry
        """
        available_dimensions = self.available_dimension_names()
        if self.system_name not in dimensions:
            logging.warning(f"error loading additional dimensions "
                            f"for {self.system_name}")
            return False
        added_dimensions = []
        for key, items in dimensions[self.system_name].items():
            if key not in available_dimensions:
                self.ureg.define(
                    f"{key} = {items['relation']}")
                added_dimensions.append(key)
            elif redefine:
                self.ureg.redefine(
                    f"{key} = {items['relation']}")
        self._additional_dimensions = self._additional_dimensions | \
                                      set(added_dimensions)
        return True

    def _load_additional_units(
            self, units: dict,
            redefine: bool = False) -> bool:
        """
        Load additional base units in registry
        """
        available_units = self.available_unit_names()
        if self.system_name not in units:
            logging.warning(f"error loading additional units "
                            f"for {self.system_name}")
            return False
        added_units = []
        for key, items in units[self.system_name].items():
            if key not in available_units:
                self.ureg.define(
                    f"{key} = {items['relation']} = {items['symbol']}")
                added_units.append(key)
            elif redefine:
                self.ureg.redefine(
                    f"{key} = {items['relation']} = {items['symbol']}")
        self._additional_units = self._additional_units | set(added_units)
        return True

    def _load_custom_dimensions(
            self,
            user: User,
            key: str = None,
            redefine: bool = False) -> bool:
        """
        Load custom units in registry
        """
        if user and type(user) == User and \
                getattr(user, 'is_authenticated', None):
            if user.is_superuser:
                qs = CustomDimension.objects.all()
            else:
                qs = CustomDimension.objects.filter(user=user)
            if key:
                qs = qs.filter(models.Q(key=key) | models.Q(key__isnull=True))
        else:
            qs = CustomDimension.objects.filter(pk=-1)
        qs = qs.filter(
            unit_system=self.system_name
        ).select_related().values('code', 'relation')
        available_dimensions = self.available_dimension_names()
        added_dimensions = []
        for cd in qs:
            props = [cd['code'], cd['relation']]
            definition = " = ".join(props)
            if cd not in available_dimensions:
                self.ureg.define(definition)
                added_dimensions.append(cd['code'])
            elif redefine:
                self.ureg.redefine(definition)
            else:
                logging.error(f"{cd['code']} already defined in registry")
        self._additional_dimensions = self._additional_dimensions | \
                                      set(added_dimensions)
        return True

    def _load_custom_units(
            self,
            user: User,
            key: str = None,
            redefine: bool = False) -> bool:
        """
        Load custom units in registry
        """
        if user and type(user) == User and \
                getattr(user, 'is_authenticated', None):
            if user.is_superuser:
                qs = CustomUnit.objects.all()
            else:
                qs = CustomUnit.objects.filter(user=user)
            if key:
                qs = qs.filter(models.Q(key=key) | models.Q(key__isnull=True))
        else:
            qs = CustomUnit.objects.filter(pk=-1)
        qs = qs.filter(unit_system=self.system_name).values(
            'code', 'relation', 'symbol', 'alias'
        )
        available_units = self.available_unit_names()
        added_units = []
        for cu in qs:
            props = [cu['code'], cu['relation']]
            if cu['symbol']:
                props.append(cu['symbol'])
            if cu['alias']:
                props.append(cu['alias'])
            definition = " = ".join(props)
            if cu['code'] not in available_units:
                self.ureg.define(definition)
                added_units.append(cu['code'])
            elif redefine:
                self.ureg.redefine(definition)
            else:
                logging.error(f"{cu['code']} already defined in registry")
        self._additional_units = self._additional_units | set(added_units)
        return True

    def _test_additional_units(self, units: dict) -> bool:
        """
        Load and check dimensionality of ADDITIONAL_BASE_UNITS values
        """
        if self.system_name not in units:
            return False
        for key in units[self.system_name].keys():
            try:
                self.unit(key).dimensionality and True
            except (pint.errors.UndefinedUnitError, AttributeError):
                return False
        return True

    def add_unit(self, code, relation, symbol, alias):
        """
        Add a new unit definition to a UnitSystem, and rebuild cache
        :param code: code of the unit
        :param relation: relation to other units (e.g.: 3 kg/m)
        :param symbol: short unit representation
        :param alias: other name for unit
        """
        self.ureg.define(f"{code} = {relation} = {symbol} = {alias}")
        self._rebuild_cache()

    def add_dimension(self, code, relation):
        """
        Add a new dimension definition to a UnitSystem, and rebuild cache
        :param code: code of the unit
        :param relation: relation to other units (e.g.: 3 kg/m)
        :param symbol: short unit representation
        :param alias: other name for unit
        """
        self.ureg.define(f"{code} = {relation}")
        self._rebuild_cache()

    @classmethod
    def available_systems(cls) -> [str]:
        """
        List of available Unit Systems
        :return: Array of string
        """
        ureg = pint.UnitRegistry(system='SI')
        return dir(ureg.sys)

    @classmethod
    def is_valid(cls, system: str) -> bool:
        """
        Check validity of the UnitSystem
        :param system: name of the unit system
        """
        us = cls()
        return system in us.available_systems()

    def current_system(self) -> pint.UnitRegistry:
        """
        Return current pint.UnitRegistry
        """
        return self.ureg

    def unit(self, unit_name):
        """
        Create a Object in the UnitSystem
        :param unit_name: name of the unit in the unit system
        """
        try:
            return Unit(unit_system=self, code=unit_name)
        except UnitNotFound:
            return None

    def available_dimension_names(self, search_term: str = None) -> [str]:
        """
        List of available units for a given Unit system
        :return: Array of names of Unit systems
        """
        if search_term:
            return [name for name in self.ureg._dimensions.keys()
                    if search_term in name]
        else:
            return list(self.ureg._dimensions.keys())

    def available_unit_names(self) -> [str]:
        """
        List of available units for a given Unit system
        :return: Array of names of Unit systems
        """
        try:
            prefixed_units_display = \
                settings.PHYSICS_PREFIXED_UNITS_DISPLAY
        except AttributeError:
            prefixed_units_display = PREFIXED_UNITS_DISPLAY
        prefixed_units = []
        for key, prefixes in prefixed_units_display.items():
            for prefix in prefixes:
                prefixed_units.append(prefix + key)
        return sorted(prefixed_units +
                      dir(getattr(self.ureg.sys, self.system_name))
                      + list(self._additional_units))

    def unit_dimensionality(self, unit: str) -> str:
        """
        User friendly representation of the dimension
        :param unit: name of the unit to display
        :return: Human readable dimension
        """
        return Unit.dimensionality_string(
            unit_system=self.system,
            unit_str=unit)

    def available_dimensions(
            self,
            *arg,
            search_term: str = None,
    ) -> {}:
        """
        Return available dimensions for the UnitSystem
        :param search_term: filter dimensions on name
        """
        dims = {}
        if self.dimensions_cache:
            dims = self.dimensions_cache
        else:
            for dim in self.available_dimension_names(search_term=search_term):
                try:
                    d = Dimension(
                        unit_system=self,
                        code=dim)
                    if d:
                        dims[dim] = d
                except DimensionNotFound as e:
                    logging.warning(f"dimension {dim} not found "
                                    f"in unit system {self.system_name}")
                    pass
        if dims:
            return dims
        return dims

    def available_units(self):
        """
        List available units
        """
        units = {}
        if self.units_cache:
            return self.units_cache
        for unit_name in self.available_unit_names():
            try:
                u = self.unit(unit_name)
                units[unit_name] = u
            except UnitNotFound:
                pass
        return units

    @property
    def _ureg_dimensions(self):
        """
        return dimensions with units
        """
        dimensions = []
        for dim in self.ureg._dimensions:
            try:
                if not self.ureg.get_compatible_units(dim):
                    continue
                dimensions.append(dim)
            except KeyError:
                continue
        return dimensions

    def _get_dimension_dimensionality(self, dimension: str) -> {}:
        """
        Return the dimensionality of a dimension
        based on the first compatible unit
        """
        try:
            for dim in self.ureg.get_compatible_units(dimension):
                return self.ureg.get_base_units(dim)[1]
        except KeyError:
            return {}

    def units_per_dimension(self, dimensions: [str] = None) -> {}:
        """
        Return units grouped by dimension
        :param dimensions: restrict list of dimensions
        """
        output = {}
        registry_dimensions = dimensions or self.available_dimension_names()
        for uname in self.available_unit_names():
            try:
                u = self.unit(uname)
                for d in [dim for dim in u.dimension_codes
                          if dim in registry_dimensions]:
                    if d in output:
                        output[d].append(u)
                    else:
                        output[d] = [u, ]
            except pint.errors.UndefinedUnitError:
                pass
        return output

    def units_per_dimensionality(self) -> {}:
        """
        List of units per dimension
        :return: dict of dimensions, with lists of unit strings
        """
        units_array = self.available_unit_names()
        output = {}
        for unit_str in units_array:
            dimension = Unit.dimensionality_string(self, unit_str)
            if dimension in output:
                output[dimension].append(unit_str)
            else:
                output[dimension] = [unit_str, ]
        return output

    @property
    def dimensionalities(self) -> [str]:
        """
        List of dimensions available in the Unit system
        :return: list of dimensions for Unit system
        """
        return set([Unit.dimensionality_string(self, unit_str)
                    for unit_str in dir(self.system)])


class Dimension:
    """
    Dimenion of a Unit
    """
    unit_system = None
    code = None
    _name = None
    dimension = None

    def __init__(self,
                 unit_system: UnitSystem,
                 code: str):
        """
        Initialize a Dimension in a UnitSystem
        """
        self.unit_system = unit_system
        self.code = code
        if code not in ['[compounded]', '[custom]'] and \
                self.unit_system.dimensions_cache and \
                code not in self.unit_system.dimensions_cache.keys():
            raise DimensionNotFound(f"Dimension {code} not found")

    @property
    def name(self):
        """
        Name of the dimension.
        """
        if self._name:
            return self._name
        else:
            code = self.code
            name = code.replace(
                '[', '').replace(
                ']', '').replace(
                '_', ' ').replace(
                '-', ' ').capitalize()
            if self.code in DIMENSIONS:
                dimension = DIMENSIONS[code]
                name = dimension['name']
            else:
                try:
                    additional_dimensions_settings = settings.PHYSICS_ADDITIONAL_DIMENSIONS
                except AttributeError:
                    additional_dimensions_settings = ADDITIONAL_DIMENSIONS
                if code in additional_dimensions_settings.keys():
                    name = additional_dimensions_settings[code]['name']
                else:
                    try:
                        cd = CustomDimension.objects.get(code=code)
                        name = cd.name
                    except CustomDimension.DoesNotExist:
                        pass
            self._name = name
            return name

    def __repr__(self):
        """
        Look beautiful
        """
        return self.code

    @property
    def pint_dimension(self):
        """
        Return the Pint dimension object
        """
        return self.unit_system.ureg._dimensions.get(self.code)

    def _prefixed_units(self, unit_names):
        """
        Add prefixed units to list of units
        :param unit_names: list of unit names
        """
        unit_list = []
        try:
            prefixed_units_display = \
                settings.PHYSICS_PREFIXED_UNITS_DISPLAY
        except AttributeError:
            prefixed_units_display = PREFIXED_UNITS_DISPLAY
        for unit, prefixes in prefixed_units_display.items():
            if unit in unit_names:
                for prefix in prefixes:
                    unit_list.append(
                        self.unit_system.unit(unit_name=prefix + unit))
        return unit_list

    @property
    def dimensionality(self):
        return self.unit_system.ureg.get_dimensionality(self.code)

    @property
    def units(self) -> [Unit]:
        """
        List of units for this dimension
        :param user: optional user for custom units
        :param key: optional key for custom units
        """
        if self.code == '[compounded]':
            return self._compounded_units
        if self.code == '[custom]':
            return self._custom_units(
                user=self.unit_system.user,
                key=self.unit_system.key)
        unit_list = \
            self.unit_system.ureg._cache.dimensional_equivalents.get(
                self.dimensionality
            ) or []
        unit_names = []
        for u in unit_list:
            try:
                unit_names.append(
                    Unit(unit_system=self.unit_system, code=u)
                )
            except UnitNotFound:
                logging.info(f"Unit {u} not found "
                             f"on unit system "
                             f"{self.unit_system.system_name}")
                continue
        unit_names.extend(self._prefixed_units(unit_names))
        return sorted(list(set(unit_names)), key=lambda x: x.name)

    @property
    def _compounded_units(self):
        """
        List units that do not belong to a dimension
        """
        compounded_units = []
        for unit in self.unit_system.available_units().values():
            if '[compounded]' in [d.code for d in unit.dimensions]:
                compounded_units.append(unit)
        return compounded_units

    def _custom_units(self, user: User, key: str = None) -> [Unit]:
        """
        Return list of custom units
        :param user: User owning the units
        :param key: optional unit key
        """
        if user and type(user) == User and \
                getattr(user, 'is_authenticated', None):
            if user.is_superuser:
                custom_units = CustomUnit.objects.all()
            else:
                custom_units = CustomUnit.objects.filter(user=user)
            if key:
                custom_units = custom_units.filter(key=key)
            return [self.unit_system.unit(cu.code) for cu in custom_units]
        else:
            return []

    @property
    def base_unit(self) -> Unit:
        """
        Base unit for this dimension in this Unit System
        """
        try:
            return self.unit_system.unit(UNIT_SYSTEM_BASE_AND_DERIVED_UNITS[
                                             self.unit_system.system_name][self.code])
        except KeyError:
            logging.info(
                f'No base unit for dimension {self.code} '
                f'in unit system {self.unit_system.system_name}')
            return None


class Unit:
    """
    Pint Unit wrapper
    """
    unit_system = None
    code = None
    unit = None
    dimensions_cache = None

    def __init__(
            self,
            unit_system: UnitSystem,
            code: str = '',
            pint_unit: pint.Unit = None
    ):
        """
        Initialize a Unit in a UnitSystem
        :param unit_system: UnitSystem instance
        :param code: code of the pint.Unit
        """
        self.unit_system = unit_system
        if pint_unit and isinstance(pint_unit, pint.Unit):
            self.code = str(pint_unit)
            self.unit = pint_unit
        elif code:
            self.code = code
            try:
                self.unit = getattr(unit_system.system, code)
                self.dimensions_cache = self.dimensions
            except pint.errors.UndefinedUnitError:
                raise UnitNotFound(f"invalid unit {code} for system")
        else:
            raise UnitNotFound("invalid unit for system")

    def __repr__(self):
        return self.code

    @classmethod
    def is_valid(cls, name: str) -> bool:
        """
        Check the validity of a unit in a UnitSystem
        """
        try:
            us_si = UnitSystem(system_name='SI')
        except UnitSystemNotFound:
            return False
        try:
            return us_si.unit(unit_name=name) and True
        except pint.errors.UndefinedUnitError:
            return False

    @property
    def name(self) -> str:
        """
        Return name of the unit from table of units
        """
        return self.unit_name(self.code)

    @property
    def symbol(self) -> str:
        """
        Return symbol for Unit
        """
        return self.unit_symbol(self.code)

    @property
    def dimension_codes(self) -> [str]:
        """
        Return dimension codes for unit
        """
        return [d.code for d in self.dimensions]

    @property
    def dimensions(self) -> [Dimension]:
        """
        Return Dimensions of Unit
        """
        if self.dimensions_cache:
            return self.dimensions_cache
        dimensions = []
        for d in self.unit_system.available_dimensions().values():
            if d.dimensionality == self.dimensionality:
                dimensions.append(d)
        if not dimensions:
            return [Dimension(unit_system=self.unit_system,
                              code='[compounded]'), ]
        else:
            return dimensions

    @staticmethod
    def base_unit(unit_str: str) -> (str, str):
        """
        Get base unit in case the unit is a prefixed unit
        :param unit_str: name of unit to check
        :return: base unit name, prefix
        """
        prefix = ''
        base_str = unit_str
        try:
            prefixed_units_display = \
                settings.PHYSICS_PREFIXED_UNITS_DISPLAY
        except AttributeError:
            prefixed_units_display = PREFIXED_UNITS_DISPLAY
        for base, prefixes in prefixed_units_display.items():
            for _prefix in prefixes:
                if unit_str == _prefix + base:
                    prefix = _prefix
                    base_str = base
        return base_str, prefix

    @staticmethod
    def unit_name(unit_str: str) -> str:
        """
        Get translated name from unit string
        :param unit_str: Name of unit
        """
        base_str, prefix = Unit.base_unit(unit_str=unit_str)
        try:
            ext_unit = UNIT_EXTENDED_DEFINITION.get(base_str)
            return prefix + str(ext_unit['name'])
        except (KeyError, TypeError):
            logging.error(f'No UNIT_EXTENDED_DEFINITION for unit {base_str}')
            return unit_str

    @staticmethod
    def unit_symbol(unit_str: str) -> str:
        """
        Static function to get symbol from unit string
        :param unit_str: Name of unit
        """
        base_str, prefix = Unit.base_unit(unit_str=unit_str)
        try:
            prefix_symbol = PREFIX_SYMBOL[prefix]
            ext_unit = UNIT_EXTENDED_DEFINITION.get(base_str)
            return prefix_symbol + ext_unit['symbol']
        except (KeyError, TypeError):
            logging.error(f'No UNIT_EXTENDED_DEFINITION for unit {base_str}')
            return ''

    @staticmethod
    def dimensionality_string(unit_system: UnitSystem, unit_str: str) -> str:
        """
        Converts pint dimensionality string to human readable string
        :param unit_system: UnitSystem
        :param unit_str: Unit name
        :return: str
        """
        ds = str(getattr(
            unit_system.ureg, unit_str
        ).dimensionality).replace('[', '').replace(']', '')
        ds = ds.replace(' ** ', '^')
        ds = ds.split()
        return ' '.join([_(d) for d in ds])

    @property
    def dimensionality(self):
        """
        Return dimensionality of a unit in Pint universe
        """
        try:
            return self.unit.dimensionality
        except KeyError:
            return ''

    @staticmethod
    def translated_name(unit_system: UnitSystem, unit_str: str) -> str:
        """
        Translated name of the unit
        """
        try:
            return '{}'.format(unit_system.ureg[unit_str])
        except KeyError:
            return unit_str

    @property
    def readable_dimension(self):
        """
        Wrapper around Unit.dimensionality_string
        """
        return Unit.dimensionality_string(
            unit_system=self.unit_system,
            unit_str=self.code)


class UnitConverter(BaseConverter):
    """
    Conversion between units
    """
    base_system = None
    base_unit = None
    user = None
    key = None

    def __init__(
            self,
            base_system: str,
            base_unit: str,
            user: User = None,
            key: key = None,
            id: str = None):
        """
        Initialize the converter. It converts a payload into a destination unit
        """
        try:
            super().__init__(id=id)
            self.base_system = base_system
            self.base_unit = base_unit
            self.user = user
            self.key = key
            self.system = UnitSystem(
                system_name=base_system,
                user=user,
                key=key)
            self.unit = Unit(
                unit_system=self.system,
                code=base_unit)
        except (UnitSystemNotFound, UnitNotFound):
            raise UnitConverterInitError

    def add_data(self, data: []) -> []:
        """
        Check data and add it to the dataset
        Return list of errors
        """
        errors = super().add_data(data)
        return errors

    def check_data(self, data):
        """
        Validates that the data contains
        system = str
        unit = str
        value = float
        date_obj ('YYYY-MM-DD')
        """
        from .serializers import QuantitySerializer
        errors = []
        for line in data:
            serializer = QuantitySerializer(data=line)
            if serializer.is_valid():
                self.data.append(serializer.create(serializer.validated_data))
            else:
                errors.append(serializer.errors)
        return errors

    @classmethod
    def load(cls,
             id: str,
             user: User = None,
             key: str = None) -> BaseConverter:
        """
        Load converter from ID
        """
        try:
            uc = super().load(id)
            uc.system = UnitSystem(
                system_name=uc.base_system,
                user=user,
                key=key)
            uc.unit = Unit(unit_system=uc.system, code=uc.base_unit)
            return uc
        except (UnitSystemNotFound, UnitNotFound, KeyError) as e:
            raise ConverterLoadError from e

    def save(self):
        """
        Save the converter to cache
        """
        system = self.system
        unit = self.unit
        self.system = None
        self.unit = None
        super().save()
        self.system = system
        self.unit = unit

    def convert(self) -> ConverterResult:
        """
        Converts data to base unit in base system
        """

        result = ConverterResult(id=self.id, target=self.base_unit)
        q_ = self.system.ureg.Quantity
        for quantity in self.data:
            try:
                pint_quantity = q_(quantity.value, quantity.unit)
                out = pint_quantity.to(self.base_unit)
                result.increment_sum(out.magnitude)
                detail = ConverterResultDetail(
                    unit=quantity.unit,
                    original_value=quantity.value,
                    date=quantity.date_obj,
                    conversion_rate=0,
                    converted_value=out.magnitude
                )
                result.detail.append(detail)
            except pint.UndefinedUnitError:
                error = ConverterResultError(
                    unit=quantity.unit,
                    original_value=quantity.value,
                    date=quantity.date_obj,
                    error=_('Undefined unit in the registry')
                )
                result.errors.append(error)
            except pint.DimensionalityError:
                error = ConverterResultError(
                    unit=quantity.unit,
                    original_value=quantity.value,
                    date=quantity.date_obj,
                    error=_('Dimensionality error, incompatible units')
                )
                result.errors.append(error)
        self.end_batch(result.end_batch())
        return result


class UnitConversionPayload:
    """
    Unit conversion payload
    """
    data = None
    base_system = ''
    base_unit = ''
    key = ''
    batch_id = ''
    eob = False

    def __init__(self,
                 base_system: UnitSystem,
                 base_unit: Unit,
                 data=None,
                 key: str = None,
                 batch_id: str = None,
                 eob: bool = False):
        """
        Initialize conversion payload
        """
        self.data = data
        self.base_system = base_system
        self.base_unit = base_unit
        self.key = key
        self.batch_id = batch_id
        self.eob = eob


class CustomDimension(models.Model):
    """
    Additional dimension for a user
    """
    AVAILABLE_SYSTEMS = (
        ('Planck', 'Planck'),
        ('SI', 'SI'),
        ('US', 'US'),
        ('atomic', 'atomic'),
        ('cgs', 'CGS'),
        ('imperial', 'imperial'),
        ('mks', 'mks'),
    )
    user = models.ForeignKey(
        User,
        related_name='dimensions',
        on_delete=models.PROTECT)
    key = models.CharField(
        "Categorization field (e.g.: customer ID)",
        max_length=255, default=None, db_index=True, null=True, blank=True)
    unit_system = models.CharField(
        "Unit system to register the unit in", max_length=20,
        choices=AVAILABLE_SYSTEMS)
    code = models.CharField(
        "technical name of the dimension (e.g.: [myDimension])",
        max_length=255)
    name = models.CharField(
        "Human readable name (e.g.: My dimension)",
        max_length=255)
    relation = models.CharField(
        "Relation to existing dimensions (e.g.: [mass]*[length]/[time])",
        max_length=255)

    class Meta:
        """
        Meta
        """
        unique_together = ('user', 'key', 'code')
        ordering = ['name', 'code']

    def validate_dimensions(self) -> [bool, str]:
        """
        Validate dimensions of the relation
        """
        dims = {}
        us = UnitSystem(system_name=self.unit_system,
                        user=self.user,
                        key=self.key)
        for dim_name in re.findall('(?P<dim>\[\w+\])', self.relation):
            try:
                dim = Dimension(unit_system=us, code=dim_name)
                dunits = dim.units
                if dunits:
                    dims[dim_name] = f"(1 * {dunits[0].code})"
            except DimensionNotFound:
                return False, f"Dimension not found {dim_name}"
        rel = self.relation
        for key, value in dims.items():
            rel = rel.replace(key, value)
        try:
            us.ureg.Quantity(rel)
        except pint.errors.UndefinedUnitError as e:
            return False, f"Incoherent units {str(e)}"
        return True, ""

    def save(self, *args, **kwargs):
        """
        Save custom unit to database
        """
        us = UnitSystem(
            system_name=self.unit_system,
            user=self.user,
            key=self.key
        )
        self.code = self.code.replace('-', '_')
        if self.code[0] != '[':
            self.code = '[' + self.code
        if self.code[-1] != ']':
            self.code = self.code + ']'
        if self.relation in us.available_dimension_names():
            raise DimensionDuplicateError("relation already exist")
        if self.code in us.available_dimension_names():
            raise DimensionDuplicateError("Dimension code already exists")
        try:
            us.add_dimension(
                code=self.code,
                relation=self.relation
            )
        except ValueError as e:
            raise DimensionValueError(str(e)) from e
        is_valid, error = self.validate_dimensions()
        if not is_valid:
            raise DimensionDimensionError(error)
        return super().save(*args, **kwargs)


class CustomUnit(models.Model):
    """
    Additional unit for a user
    """
    AVAILABLE_SYSTEMS = (
        ('Planck', 'Planck'),
        ('SI', 'SI'),
        ('US', 'US'),
        ('atomic', 'atomic'),
        ('cgs', 'CGS'),
        ('imperial', 'imperial'),
        ('mks', 'mks'),
    )
    user = models.ForeignKey(
        User,
        related_name='units',
        on_delete=models.PROTECT)
    key = models.CharField(
        "Categorization field (e.g.: customer ID)",
        max_length=255, default=None, db_index=True, null=True, blank=True)
    unit_system = models.CharField(
        "Unit system to register the unit in", max_length=20,
        choices=AVAILABLE_SYSTEMS)
    code = models.SlugField("technical name of the unit (e.g.: myUnit)")
    name = models.CharField(
        "Human readable name (e.g.: My Unit)",
        max_length=255)
    relation = models.CharField(
        "Relation to an existing unit (e.g.: 12 kg*m/s)", max_length=255)
    symbol = models.CharField(
        "Symbol to use in a formula (e.g.: myu)",
        max_length=20, blank=True, null=True)
    alias = models.CharField(
        "Other code for this unit (e.g.: mybu)",
        max_length=20, null=True, blank=True)

    class Meta:
        """
        Meta
        """
        unique_together = ('user', 'key', 'code')
        ordering = ['name', 'code']

    def save(self, *args, **kwargs):
        """
        Save custom unit to database
        """
        us = UnitSystem(system_name=self.unit_system)
        self.code = self.code.replace('-', '_')
        if self.symbol:
            self.symbol = self.symbol.replace('-', '_')
        if self.alias:
            self.alias = self.alias.replace('-', '_')
        if self.code in us.available_unit_names():
            raise UnitDuplicateError
        try:
            us.add_unit(
                code=self.code,
                relation=self.relation,
                symbol=self.symbol,
                alias=self.alias)
        except ValueError as e:
            raise UnitValueError(str(e)) from e
        try:
            us.unit(self.code).unit.dimensionality
        except (pint.errors.UndefinedUnitError, AttributeError) as e:
            raise UnitDimensionError(str(e))
        return super().save(*args, **kwargs)


def unit_system_obj(self, *args, **kwargs):
    """
    Returns a UnitSystem object from a system name
    Doesn't take context into account
    """
    return UnitSystem(system_name=self.unit_system)


# Add unit_system_obj attribute to Country class
setattr(Country, 'unit_system_obj', unit_system_obj)
