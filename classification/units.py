"""Conservative explicit-unit compatibility. Missing/ambiguous units pass.

This is a bounded registry, not inference from property names. Unknown units
remain unknown; no regex substring matching such as 'h' inside 'strength'.
"""
import re
import unicodedata

GROUPS = {
    "pressure": ["Pa", "kPa", "MPa", "GPa", "psi", "N/mm2", "N/mm^2"],
    "temperature": ["℃", "°C", "°F", "K", "摄氏度", "开尔文"],
    "time": ["s", "ms", "μs", "us", "min", "h", "hour", "秒", "分钟", "小时"],
    "length": ["m", "cm", "mm", "μm", "um", "nm", "pm", "Å"],
    "area": ["m2", "m^2", "cm2", "cm^2", "mm2", "mm^2"],
    "volume": ["m3", "m^3", "cm3", "cm^3", "mm3", "mm^3"],
    "density": ["g/cm3", "g/cm^3", "kg/m3", "kg/m^3"],
    "fraction": ["%", "wt%", "wt.%", "at%", "at.%", "vol%", "百分比"],
    "frequency": ["Hz", "kHz", "MHz", "GHz", "s^-1", "s-1", "1/s"],
    "velocity": ["m/s", "mm/s", "mm/min", "μm/s", "um/s"],
    "energy": ["J", "kJ", "eV", "meV"],
    "energy_per_mole": ["J/mol", "kJ/mol"],
    "force": ["N", "kN", "mN"],
    "mass": ["kg", "g", "mg", "μg"],
    "voltage": ["V", "mV", "kV"],
    "current": ["A", "mA", "μA"],
    "resistance": ["Ω", "ohm", "kΩ", "MΩ"],
    "resistivity": ["Ω·m", "Ω*m", "Ω m", "ohm*m", "Ω·cm"],
    "conductivity": ["S/m", "S/cm"],
    "thermal_conductivity": ["W/(m·K)", "W/mK", "W/(m*K)"],
    "heat_capacity": ["J/(kg·K)", "J/(g·K)", "J/kgK"],
    "toughness": ["MPa√m", "MPa·m^0.5", "MPa*m^0.5"],
    "dynamic_viscosity": ["Pa·s", "mPa·s", "Pa*s", "mPa*s"],
    "kinematic_viscosity": ["m2/s", "mm2/s"],
    "specific_area": ["m2/g", "m^2/g"],
    "angle": ["°", "deg", "rad"],
}


def canon(text):
    return unicodedata.normalize("NFKC", str(text)).replace("µ", "μ")


REGISTRY = {canon(u): d for d, units in GROUPS.items() for u in units}
PATTERN = re.compile(r"(?<![A-Za-z0-9])(" + "|".join(
    re.escape(u) for u in sorted(REGISTRY, key=len, reverse=True)) + r")(?![A-Za-z0-9])")


def dimensions(text, explicit=False):
    text = canon(text)
    regions = [text] if explicit else []
    if not explicit:
        # Accept brackets, an explicit unit phrase or a trailing unit suffix.
        regions.extend(re.findall(r"[\[(]([^\])]+)[\])]", text))
        regions.extend(re.findall(r"(?:单位(?:为|是)?|unit[s]?\s*[:=]?|量纲(?:为)?)\s*([^，。；;\n]+)", text))
        suffix = re.search(r"[\s_]([^\s]+)$", text)
        if suffix and suffix.group(1) in REGISTRY:
            regions.append(suffix.group(1))
        if "%" in text:
            regions.append("%")
    found = set()
    for region in regions:
        for m in PATTERN.finditer(region):
            # An adjacent unparsed compound makes the dimension uncertain.
            if (m.start() and region[m.start()-1] in "/*·√^") or (
                    m.end() < len(region) and region[m.end()] in "/*·√^"):
                continue
            found.add(REGISTRY[m.group(1)])
    return found if len(found) == 1 else set()


def compatibility(source, target):
    a = dimensions(source.get("original_field", "")) | dimensions(source.get("description", ""))
    b = dimensions(target.get("description", ""))
    if len(a) != 1 or len(b) != 1:
        return True, "unknown_or_ambiguous"
    return a == b, "same_dimension" if a == b else "incompatible"
