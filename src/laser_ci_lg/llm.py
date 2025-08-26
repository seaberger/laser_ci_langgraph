import os, json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

SCHEMA = {
    "name": "CanonicalSpecs",
    "schema": {
        "type": "object",
        "properties": {
            "wavelength_nm": {"type": "number", "nullable": True},
            "output_power_mw_nominal": {"type": "number", "nullable": True},
            "output_power_mw_min": {"type": "number", "nullable": True},
            "rms_noise_pct": {"type": "number", "nullable": True},
            "power_stability_pct": {"type": "number", "nullable": True},
            "linewidth_mhz": {"type": "number", "nullable": True},
            "linewidth_nm": {"type": "number", "nullable": True},
            "m2": {"type": "number", "nullable": True},
            "beam_diameter_mm": {"type": "number", "nullable": True},
            "beam_divergence_mrad": {"type": "number", "nullable": True},
            "polarization": {"type": "string", "nullable": True},
            "modulation_analog_hz": {"type": "number", "nullable": True},
            "modulation_digital_hz": {"type": "number", "nullable": True},
            "ttl_shutter": {"type": "boolean", "nullable": True},
            "fiber_output": {"type": "boolean", "nullable": True},
            "fiber_na": {"type": "number", "nullable": True},
            "fiber_mfd_um": {"type": "number", "nullable": True},
            "warmup_time_min": {"type": "number", "nullable": True},
            "interfaces": {
                "type": "array",
                "items": {"type": "string"},
                "nullable": True,
            },
            "dimensions_mm": {
                "type": "object",
                "nullable": True,
                "properties": {
                    "x": {"type": "number"},
                    "y": {"type": "number"},
                    "z": {"type": "number"},
                },
                "required": [],
            },
            "vendor_fields": {"type": "object", "nullable": True},
        },
        "required": [],
    },
}

SYSTEM = (
    "You convert raw vendor laser specs into a canonical JSON schema for CW diode/instrumentation lasers. "
    "Return ONLY JSON with these exact fields:\n"
    "- wavelength_nm: number (e.g., 488 for '488 nm')\n"
    "- output_power_mw_nominal: number (e.g., 100 for '100 mW', 50000 for '50 W')\n"
    "- output_power_mw_min: number (minimum guaranteed power)\n"
    "- rms_noise_pct: number (e.g., 0.25 for '<0.25%')\n"
    "- power_stability_pct: number (e.g., 1 for '±1%')\n"
    "- linewidth_mhz: number (convert from nm/pm if needed)\n"
    "- linewidth_nm: number (convert from MHz/GHz if needed)\n"
    "- m2: number (e.g., 1.3 for 'M²<1.3')\n"
    "- beam_diameter_mm: number (e.g., 0.7 for '0.7 mm')\n"
    "- beam_divergence_mrad: number\n"
    "- polarization: string (e.g., 'Linear', 'Circular')\n"
    "- modulation_analog_hz: number (e.g., 350000 for '350 kHz')\n"
    "- modulation_digital_hz: number (e.g., 1000000 for '1 MHz')\n"
    "- ttl_shutter: boolean\n"
    "- fiber_output: boolean\n"
    "- fiber_na: number\n"
    "- fiber_mfd_um: number\n"
    "- warmup_time_min: number\n"
    "- interfaces: array of strings (e.g., ['USB', 'RS-232'])\n"
    "- dimensions_mm: object with x, y, z numeric fields\n"
    "- vendor_fields: object with any specs you can't map\n\n"
    "IMPORTANT: Return direct numeric values, NOT nested objects. "
    "For '<X' or '≤X' use X. For ranges use typical/middle value. "
    "Convert all units appropriately (W to mW, kHz to Hz, etc.)."
)


def llm_normalize(
    raw_specs: dict, free_text: str = "", model: str | None = None
) -> dict:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    prompt = {"raw_specs": raw_specs, "context": free_text[:8000]}
    resp = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": json.dumps(prompt)}
        ],
        response_format={"type": "json_object"},
    )
    out = resp.choices[0].message.content  # JSON string
    return json.loads(out)
