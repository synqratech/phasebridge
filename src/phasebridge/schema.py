# src/phasebridge/schema.py
from __future__ import annotations
from typing import Any, Dict, Optional
import json
import pathlib

try:
    import jsonschema  # optional, nice-to-have
    _HAVE_JSONSCHEMA = True
except Exception:
    jsonschema = None  # type: ignore
    _HAVE_JSONSCHEMA = False

from .pif import PIF, validate_pif

# ---- Minimal JSON Schema for PIF v1 core (strict core) ----
_DEFAULT_PIF_V1_SCHEMA: Dict[str, Any] = {
    "title": "PIF v1 (core)",
    "type": "object",
    "required": ["schema", "theta", "meta"],
    "properties": {
        "pif_version": {"type": "string"},  # optional; SemVer if desired
        "domain": {"type": "string"},
        "schema": {
            "type": "object",
            "required": ["alphabet"],
            "properties": {
                "alphabet": {
                    "type": "object",
                    "required": ["type", "M"],
                    "properties": {
                        "type": {"const": "uint"},
                        "M": {
                            "type": "integer",
                            "minimum": 2,
                            "maximum": 4294967296
                        }
                    },
                    "additionalProperties": True
                },
                "sampling": {
                    "type": "object",
                    "properties": {
                        "fs": {"type": "number", "exclusiveMinimum": 0}
                    },
                    "additionalProperties": True
                }
            },
            "additionalProperties": True
        },
        "numeric": {
            "type": "object",
            "properties": {
                "dtype": {"type": "string"},
                "phase_wrap": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 2,
                    "maxItems": 2
                }
            },
            "additionalProperties": True
        },
        "codec": {
            "type": "object",
            "properties": {
                "forward": {"type": "string"},
                "inverse": {"type": "string"}
            },
            "additionalProperties": True
        },
        "theta": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "number"}
        },
        "amp": {
            "oneOf": [
                {"type": "number", "minimum": 0},
                {
                    "type": "array",
                    "items": {"type": "number", "minimum": 0}
                }
            ]
        },
        "meta": {
            "type": "object",
            "required": ["note"],
            "properties": {
                "note": {
                    "type": "string",
                    "pattern": r"^(no_processing|processed:.+)$"
                },
                "hash_raw": {
                    "type": "string",
                    "pattern": r"^sha256:[0-9a-fA-F]{64}$"
                },
                "codec_hash": {
                    "type": "string",
                    "pattern": r"^sha256:[0-9a-fA-F]{64}$"
                },
                "codec": {"type": "string"}
            },
            "additionalProperties": True
        }
    },
    "additionalProperties": True
}


# ---- Public API ----

def get_default_schema() -> Dict[str, Any]:
    """
    Return the built-in JSON Schema for PIF v1 (core).
    """
    # return a copy so external modifications don't affect the module constant
    import copy
    return copy.deepcopy(_DEFAULT_PIF_V1_SCHEMA)


def load_schema_file(path: str | pathlib.Path) -> Dict[str, Any]:
    """
    Load JSON Schema from a file.
    """
    p = pathlib.Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Schema file not found: {p}")
    text = p.read_text(encoding="utf-8")
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in schema file: {p}\n{e}") from e
    if not isinstance(obj, dict):
        raise ValueError("Schema root must be an object")
    return obj


def validate_pif_dict(
    pif_obj: Dict[str, Any],
    schema: Optional[Dict[str, Any]] = None,
    use_jsonschema: bool = True,
    also_runtime_validate: bool = True
) -> None:
    """
    Validate a PIF dictionary against JSON Schema (if use_jsonschema is True and library available)
    and/or via strict runtime validation (PIF.from_dict + validate_pif).

    Raises:
        jsonschema.ValidationError (if jsonschema is active and validation fails),
        ValueError (if runtime validation fails)
    """
    if schema is None:
        schema = get_default_schema()

    # JSON Schema validation (if enabled and available)
    if use_jsonschema and _HAVE_JSONSCHEMA:
        jsonschema.validate(instance=pif_obj, schema=schema)  # type: ignore

    if also_runtime_validate:
        # runtime validation: convert to PIF + strict checks (dtype, phase, amp, meta)
        p = PIF.from_dict(pif_obj, validate=True)
        # PIF.from_dict(validate=True) already calls validate_pif(p)
        # Additional business validation could be added here if needed.

def validate_pif_json(
    pif_json: str,
    schema: Optional[Dict[str, Any]] = None,
    use_jsonschema: bool = True,
    also_runtime_validate: bool = True
) -> None:
    """
    Validate PIF given as a JSON string.
    """
    try:
        obj = json.loads(pif_json)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid PIF JSON: {e}") from e
    if not isinstance(obj, dict):
        raise ValueError("PIF JSON root must be an object")
    validate_pif_dict(
        pif_obj=obj,
        schema=schema,
        use_jsonschema=use_jsonschema,
        also_runtime_validate=also_runtime_validate,
    )
