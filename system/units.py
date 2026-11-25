"""Shared deterministic conversion for ingestion and query thresholds."""
from copy import deepcopy
import math
from pint import UnitRegistry

REGISTRY = UnitRegistry(autoconvert_offset_to_baseunit=True)
ALIASES = {'米':'m', '厘米':'cm', '毫米':'mm', '微米':'um', '℃':'degC',
           '°C':'degC', '摄氏度':'degC', '°F':'degF', '℉':'degF',
           'MPa':'MPa', 'g/cm3':'g/cm**3', 'kg/m3':'kg/m**3'}

def unit_name(unit):
    text = (unit or '').strip()
    return ALIASES.get(text, text)

def convert(value, source, target):
    source, target = unit_name(source), unit_name(target)
    if not source or not target:
        raise ValueError('Both source and standard units are required')
    if isinstance(value, bool):
        raise ValueError('Boolean is not a measurement')
    try:
        number = float(value)
        result = REGISTRY.Quantity(number, source).to(target).magnitude
    except Exception as exc:
        raise ValueError('Invalid value or incompatible/unsupported units: %s -> %s' % (source, target)) from exc
    if not math.isfinite(number) or not math.isfinite(result):
        raise ValueError('Nonfinite measurement')
    return float(result)

def standard_units(cur):
    cur.execute('SELECT property_name,standard_unit FROM matsir_property_unit')
    return {r['property_name']:r['standard_unit'] for r in cur.fetchall()}

def normalize_sir(sir, units):
    result = deepcopy(sir)
    for group in result.get('groups', []):
        for condition in group.get('conditions', []):
            source = condition.get('unit')
            target = units.get(condition['field'])
            value = condition.get('value')
            if source and not target:
                raise ValueError('Configure standard unit for '+condition['field'])
            if target and value is not None:
                # An omitted query unit denotes the property's registered unit.
                values = value if isinstance(value, list) else [value]
                converted = [convert(v, source or target, target) for v in values]
                condition['source_value'] = value
                condition['source_unit'] = source or target
                condition['value'] = converted if isinstance(value, list) else converted[0]
            if target:
                condition['unit'] = target
    return result
