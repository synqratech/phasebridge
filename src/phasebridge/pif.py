# src/phasebridge/pif.py
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Dict, Union, Optional
import numpy as np
import json
import re

TWO_PI = 2.0 * np.pi

def _wrap_phase(theta: np.ndarray) -> np.ndarray:
    """Wrap phases to [0, 2π)."""
    th = np.asarray(theta, dtype=np.float64)
    th = np.mod(th, TWO_PI)
    th[np.isclose(th, TWO_PI)] = 0.0
    return th

def _validate_schema_dict(schema: Dict[str, Any]) -> None:
    if not isinstance(schema, dict):
        raise ValueError("schema must be a dict")
    if "alphabet" not in schema or not isinstance(schema["alphabet"], dict):
        raise ValueError("schema.alphabet must be provided as dict")
    alphabet = schema["alphabet"]
    if alphabet.get("type") != "uint":
        raise ValueError("schema.alphabet.type must be 'uint'")
    M = alphabet.get("M", None)
    if not (isinstance(M, int) and 2 <= M <= (1<<32)):
        raise ValueError("schema.alphabet.M must be int in [2, 2^32]")
    if "sampling" in schema:
        samp = schema["sampling"]
        if not isinstance(samp, dict):
            raise ValueError("schema.sampling must be dict")
        fs = samp.get("fs", None)
        if fs is not None:
            if not (isinstance(fs, (int, float)) and fs > 0):
                raise ValueError("schema.sampling.fs must be positive number if provided")

def _validate_meta_dict(meta: Dict[str, Any]) -> None:
    if not isinstance(meta, dict):
        raise ValueError("meta must be a dict")
    note = meta.get("note", None)
    if note is None:
        raise ValueError("meta.note must be provided")
    if not (note == "no_processing" or (isinstance(note, str) and note.startswith("processed:"))):
        raise ValueError("meta.note must be 'no_processing' or 'processed:<ops>'")
    hr = meta.get("hash_raw", None)
    if hr is not None:
        if not (isinstance(hr, str) and hr.startswith("sha256:") and len(hr) >= len("sha256:")+64):
            raise ValueError("meta.hash_raw must be 'sha256:<64 hex chars>' if provided")
        hx = hr.split(":",1)[1]
        if not re.fullmatch(r"[0-9a-fA-F]{64}", hx):
            raise ValueError("meta.hash_raw hex invalid")
    ch = meta.get("codec_hash", None)
    if ch is not None:
        if not (isinstance(ch, str) and ch.startswith("sha256:") and len(ch) >= len("sha256:")+64):
            raise ValueError("meta.codec_hash must be 'sha256:<64 hex chars>' if provided")
        hx = ch.split(":",1)[1]
        if not re.fullmatch(r"[0-9a-fA-F]{64}", hx):
            raise ValueError("meta.codec_hash hex invalid")
    if "codec" in meta and not isinstance(meta["codec"], str):
        raise ValueError("meta.codec must be a string if provided")

def _dtype_is_float64(arr: np.ndarray) -> bool:
    return isinstance(arr, np.ndarray) and arr.dtype == np.float64

@dataclass
class PIF:
    """
    Phase Interchange Format (PIF) — strict minimal core for v1.
    - theta: float64 array of shape (N,); phases wrapped to [0, 2π).
    - amp: float or float64 array; MVP uses 1.0 (scalar).
    - schema: dict with at least {alphabet: {type: "uint", M: int}} and optional sampling.fs
    - meta: dict with at least note: "no_processing" in MVP.
    """
    schema: Dict[str, Any]
    theta: np.ndarray
    amp: Union[float, np.ndarray] = 1.0
    meta: Dict[str, Any] = None

    def __post_init__(self):
        self.theta = _wrap_phase(np.asarray(self.theta, dtype=np.float64))
        if isinstance(self.amp, np.ndarray):
            if self.amp.dtype != np.float64:
                self.amp = self.amp.astype(np.float64)
            if self.amp.shape != self.theta.shape:
                raise ValueError("amp array shape must match theta shape")
        else:
            self.amp = float(self.amp)
        if self.meta is None:
            self.meta = {"note": "no_processing"}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema": self.schema,
            "theta": self.theta.astype(np.float64).tolist(),
            "amp": self.amp if not isinstance(self.amp, np.ndarray) else self.amp.astype(np.float64).tolist(),
            "meta": self.meta,
        }

    def to_json(self, indent: Optional[int] = 0) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent if indent is not None else 0)

    @staticmethod
    def from_dict(d: Dict[str, Any], validate: bool = True) -> "PIF":
        theta = np.asarray(d["theta"], dtype=np.float64)
        amp_val = d.get("amp", 1.0)
        amp = np.asarray(amp_val, dtype=np.float64) if isinstance(amp_val, list) else float(amp_val)
        p = PIF(schema=d["schema"], theta=theta, amp=amp, meta=d.get("meta", {"note":"no_processing"}))
        if validate:
            validate_pif(p)
        return p

    @staticmethod
    def from_json(s: str, validate: bool = True) -> "PIF":
        d = json.loads(s)
        return PIF.from_dict(d, validate=validate)

def validate_pif(p: PIF) -> None:
    """Validate PIF object against minimal v1 core constraints."""
    _validate_schema_dict(p.schema)
    if not _dtype_is_float64(p.theta):
        raise ValueError("theta must be float64 array")
    if np.any(p.theta < 0.0) or np.any(p.theta >= TWO_PI + 1e-15):
        raise ValueError("theta must be in [0, 2π)")
    if isinstance(p.amp, np.ndarray):
        if not _dtype_is_float64(p.amp):
            raise ValueError("amp array must be float64")
        if p.amp.shape != p.theta.shape:
            raise ValueError("amp array shape must match theta shape")
        if np.any(p.amp < 0):
            raise ValueError("amp must be non-negative")
    else:
        if not isinstance(p.amp, float):
            raise ValueError("amp scalar must be float")
        if p.amp < 0.0:
            raise ValueError("amp must be non-negative")
    _validate_meta_dict(p.meta)
