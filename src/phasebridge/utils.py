# src/phasebridge/utils.py
from __future__ import annotations
from typing import Any, Dict, Tuple
import numpy as np
import hashlib

TWO_PI = 2.0 * np.pi

# ---------- Hashes / Bytes ----------

def sha256_bytes(b: bytes) -> str:
    """Return sha256 hex string (without prefix)."""
    return hashlib.sha256(b).hexdigest()

def prefixed_sha256_bytes(b: bytes) -> str:
    """Return 'sha256:<hex>' — compatible with meta.hash_raw/meta.codec_hash."""
    return f"sha256:{sha256_bytes(b)}"

def sha256_of_array(arr: np.ndarray, ensure_contiguous: bool = True) -> str:
    """Compute sha256 of array bytes (view without copy when possible)."""
    a = np.ascontiguousarray(arr) if ensure_contiguous else arr
    return prefixed_sha256_bytes(a.tobytes())


# ---------- Types / Checks ----------

def is_uint_array(x: np.ndarray) -> bool:
    return isinstance(x, np.ndarray) and np.issubdtype(x.dtype, np.unsignedinteger)

def is_float64_array(x: np.ndarray) -> bool:
    return isinstance(x, np.ndarray) and x.dtype == np.float64

def min_uint_dtype(M: int):
    """Minimal unsigned dtype that covers an alphabet of size M."""
    if M <= 255:
        return np.uint8
    if M <= 65535:
        return np.uint16
    if M <= 4294967295:
        return np.uint32
    return np.uint64

def as_uint_array(x: np.ndarray, dtype=None) -> np.ndarray:
    """Convert to an unsigned integer array (casting dtype if necessary)."""
    if dtype is None:
        if not is_uint_array(x):
            raise TypeError("Expected unsigned integer array or specify dtype=")
        return np.ascontiguousarray(x)
    dt = np.dtype(dtype)
    if not np.issubdtype(dt, np.unsignedinteger):
        raise TypeError("dtype must be an unsigned integer dtype")
    return np.ascontiguousarray(x.astype(dt, copy=False))


# ---------- Phases ----------

def wrap_phase(theta: np.ndarray) -> np.ndarray:
    """Wrap phases into [0, 2π) and ensure float64."""
    th = np.asarray(theta, dtype=np.float64)
    th = np.mod(th, TWO_PI)
    th[np.isclose(th, TWO_PI)] = 0.0
    return th

def nearest_phase_indices(theta: np.ndarray, M: int) -> np.ndarray:
    """Convert phases back to lattice indices {0..M-1} using nearest node."""
    th = wrap_phase(theta)
    n = np.rint(M * th / TWO_PI).astype(np.int64) % M
    return n

def grid_phases_from_uint(x_uint: np.ndarray, M: int) -> np.ndarray:
    """Convert discrete symbols {0..M-1} to phase lattice nodes (float64)."""
    n = np.asarray(x_uint, dtype=np.int64) % M
    return (TWO_PI * n / M).astype(np.float64)


# ---------- Utilities ----------

def safe_len(obj: Any) -> int:
    try:
        return len(obj)  # type: ignore
    except Exception:
        return 0

def verify_roundtrip(x_uint: np.ndarray, codec, schema: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    """
    Quick sanity-check round-trip: encode→decode and compare with the original.
    Returns (ok, report), where report contains sizes/types.
    """
    p = codec.encode(x_uint, schema)
    x_rec = codec.decode(p)
    ok = np.array_equal(x_uint, x_rec)
    report = {
        "ok": ok,
        "N": int(x_uint.size),
        "dtype_in": str(x_uint.dtype),
        "dtype_out": str(x_rec.dtype),
        "codec": getattr(codec, "_codec_id", lambda: str(codec))(),
        "M": int(getattr(codec, "M", -1)),
    }
    return ok, report
