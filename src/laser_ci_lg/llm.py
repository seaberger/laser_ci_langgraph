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
    "You convert raw vendor laser specs into a *canonical JSON* schema for CW diode/instrumentation lasers. "
    "Return ONLY JSON. Extract numbers and units (nm, mW, %, MHz/mrad/mm). Prefer nominal values when ranges are given. "
    "Populate vendor_fields with additional items you can't map."
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
