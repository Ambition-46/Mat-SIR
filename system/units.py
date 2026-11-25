"""Shared deterministic conversion for ingestion and query thresholds."""
from copy import deepcopy
import math
import re
from pint import UnitRegistry

REGISTRY = UnitRegistry(autoconvert_offset_to_baseunit=True)
REGISTRY.define('mass_fraction = [mass_fraction]')
REGISTRY.define('wt_percent = 0.01 * mass_fraction')
REGISTRY.define('atomic_fraction = [atomic_fraction]')
REGISTRY.define('at_percent = 0.01 * atomic_fraction')
ALIASES = {'米':'m', '厘米':'cm', '毫米':'mm', '微米':'um', '℃':'degC',
           '°C':'degC', '摄氏度':'degC', '°F':'degF', '℉':'degF',
           'MPa':'MPa', 'μm':'um', 'wt%':'wt_percent', 'wt％':'wt_percent', 'wt％':'wt_percent', 'wt%':'wt_percent', 'wt％':'wt_percent', 'wt％':'wt_percent', 'wt%':'wt_percent', 'wt％':'wt_percent', 'wt％':'wt_percent', 'g/cm3':'g/cm**3', 'kg/m3':'kg/m**3'}

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

def description_unit(description):
    """Read explicit unit metadata; never infer a unit from a property name."""
    text = description or ''
    if re.search(r'单位(?:依|随|不|未知|未指定)|units?\s+(?:depend|vary|unknown)', text, re.I):
        return None
    candidates = re.findall(r'(?:单位(?:为|是)?|\bunits?\s*(?:is|are)?)[：:\s]*([^，,。;；\n]+)', text, re.I)
    candidates += re.findall(r'[（(]([^()（）]+)[）)]', text)
    valid = set()
    for candidate in candidates:
        candidate = candidate.strip().rstrip('.')
        if re.search(r'或|或者|\bor\b|、', candidate, re.I):
            return None
        candidate = unit_name(candidate)
        try:
            REGISTRY.Unit(candidate)
        except Exception:
            continue
        if candidate:
            valid.add(candidate)
    return next(iter(valid)) if len(valid) == 1 else None


def standard_units(cur):
    cur.execute('SELECT property_name,property_description FROM property_table')
    return {r['property_name']: description_unit(r['property_description']) for r in cur.fetchall()}


def normalize_value(value, source, target):
    # No explicit input unit means no detected discrepancy: retain the value.
    if not source:
        return value
    if not target:
        raise ValueError('Matched property description has no unambiguous unit')
    if unit_name(source) == unit_name(target):
        return value
    return convert(value, source, target)


def normalize_sir(sir, units):
    result = deepcopy(sir)
    for group in result.get('groups', []):
        for condition in group.get('conditions', []):
            source = condition.get('unit')
            target = units.get(condition['field'])
            value = condition.get('value')
            if value is not None and source:
                values = value if isinstance(value, list) else [value]
                converted = [normalize_value(v, source, target) for v in values]
                if unit_name(source) != unit_name(target):
                    condition['source_value'] = value
                    condition['source_unit'] = source
                    condition['value'] = converted if isinstance(value, list) else converted[0]
                    condition['unit'] = target
    return result
