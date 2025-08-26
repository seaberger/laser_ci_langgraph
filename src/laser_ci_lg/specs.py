import re
from typing import Optional, Any

CANONICAL_SPEC_KEYS = {
    "wavelength_nm",
    "output_power_mw_nominal",
    "output_power_mw_min",
    "rms_noise_pct",
    "power_stability_pct",
    "linewidth_mhz",
    "linewidth_nm",
    "m2",
    "beam_diameter_mm",
    "beam_divergence_mrad",
    "polarization",
    "modulation_analog_hz",
    "modulation_digital_hz",
    "ttl_shutter",
    "fiber_output",
    "fiber_na",
    "fiber_mfd_um",
    "warmup_time_min",
    "interfaces",
    "dimensions_mm",
}

KEY_MAP = {
    r"^wavelength(s)?$|^λ$|^lambda$|^emission wavelength$": "wavelength_nm",
    r"^output power$|^optical power$|^cw power$|^typ\. power$|^maximum output power$": "output_power_mw_nominal",
    r"^min\. power$|^power min$": "output_power_mw_min",
    r"^(rms )?noise( \(.*\))?$|^intensity noise$|^rms noise$": "rms_noise_pct",
    r"^power stability$|^long-?term (power )?stability$|^ltp$": "power_stability_pct",
    r"^m.?2$|^m\^2$|^m²$|^beam quality$": "m2",
    r"^beam diameter.*$|^output beam diameter$": "beam_diameter_mm",
    r"^beam divergence$|^half-angle divergence$": "beam_divergence_mrad",
    r"^polarization( ratio)?$": "polarization",
    r"^linewidth$|^spectral linewidth$|^fwhm$": "linewidth_mhz",
    r"^analog modulation$|^am bandwidth$": "modulation_analog_hz",
    r"^digital modulation$|^ttl modulation$|^blanking rate$|^modulation depth$": "modulation_digital_hz",
    r"^electronic shutter$|^laser inhibit$": "ttl_shutter",
    r"^fiber output$|^fiber delivery$": "fiber_output",
    r"^fiber na$|^na$": "fiber_na",
    r"^mode field diameter$|^mfd$": "fiber_mfd_um",
    r"^interfaces?$|^control interface$": "interfaces",
    r"^warm-?up time$": "warmup_time_min",
    r"^dimensions?$|^size$|^footprint$": "dimensions_mm",
}


def canonical_key(vendor_key: str) -> Optional[str]:
    k = vendor_key.strip().lower()
    for pattern, ck in KEY_MAP.items():
        if re.match(pattern, k):
            return ck
    return None


def parse_value_to_unit(key: str, value: str) -> Any:
    v = value.strip()

    def to_float(x: str):
        try:
            # Handle comparison operators
            x = re.sub(r'^[<>≤≥]\s*', '', x)
            # Remove commas from numbers
            x = x.replace(',', '')
            return float(x)
        except:
            return None

    if key == "wavelength_nm":
        m = re.search(r"([\d\.]+)\s*nm", v, re.I)
        return to_float(m.group(1)) if m else to_float(v)

    if key in {"output_power_mw_nominal", "output_power_mw_min"}:
        m = re.search(r"([\d\.]+)\s*(mW|W)", v, re.I)
        if not m:
            return to_float(v)
        num, unit = float(m.group(1)), m.group(2).lower()
        return num * 1000.0 if unit == "w" else num

    if key in {"rms_noise_pct", "power_stability_pct"}:
        m = re.search(r"([\d\.]+)\s*%", v, re.I)
        return to_float(m.group(1)) if m else to_float(v)

    if key in {"linewidth_mhz", "linewidth_nm"}:
        mhz = re.search(r"([\d\.]+)\s*MHz", v, re.I)
        if mhz:
            return to_float(mhz.group(1))
        nm = re.search(r"([\d\.]+)\s*(nm|pm)", v, re.I)
        if nm:
            return to_float(nm.group(1))
        return to_float(v)

    if key == "beam_diameter_mm":
        m = re.search(r"([\d\.]+)\s*mm", v, re.I)
        return to_float(m.group(1)) if m else to_float(v)

    if key == "beam_divergence_mrad":
        m = re.search(r"([\d\.]+)\s*mrad", v, re.I)
        return to_float(m.group(1)) if m else to_float(v)

    if key == "m2":
        return to_float(v)

    if key in {"modulation_analog_hz", "modulation_digital_hz"}:
        m = re.search(r"([\d\.]+)\s*(Hz|kHz|MHz)", v, re.I)
        if not m:
            return to_float(v)
        factor = {"hz": 1, "khz": 1e3, "mhz": 1e6}[m.group(2).lower()]
        return float(m.group(1)) * factor

    if key == "ttl_shutter":
        return v.lower() in {"yes", "true", "1"} or "shutter" in v.lower()

    if key == "fiber_output":
        return v.lower() in {
            "yes",
            "true",
            "1",
            "smf",
            "mmf",
            "fiber",
            "integrated fiber",
        }

    if key == "fiber_na":
        m = re.search(r"na\s*=?\s*([\d\.]+)", v, re.I)
        return float(m.group(1)) if m else to_float(v)

    if key == "fiber_mfd_um":
        m = re.search(r"([\d\.]+)\s*µ?m", v, re.I)
        return float(m.group(1)) if m else to_float(v)

    if key == "warmup_time_min":
        m = re.search(r"([\d\.]+)\s*(min|s)", v, re.I)
        if not m:
            return to_float(v)
        num, unit = float(m.group(1)), m.group(2).lower()
        return num / 60.0 if unit == "s" else num

    if key == "interfaces":
        import re as _re

        toks = _re.split(r"[,/;]| and ", v, flags=_re.I)
        return [t.strip().upper().replace("RS232", "RS-232") for t in toks if t.strip()]

    if key == "dimensions_mm":
        m = re.search(r"([\d\.]+)\s*[x×]\s*([\d\.]+)\s*[x×]\s*([\d\.]+)\s*mm", v, re.I)
        if m:
            return {
                "x": float(m.group(1)),
                "y": float(m.group(2)),
                "z": float(m.group(3)),
            }
        return None

    if key == "polarization":
        return v.upper()
    return v
