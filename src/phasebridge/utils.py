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


# ---------- Numeric policy (Float32 support) ----------

def is_float32_safe_for_M(M: int) -> bool:
    """
    Conservative safety predicate for storing θ in float32 for given M.
    Chosen as M <= 65536 to guarantee decode(round-trip) with float64 decoder.
    """
    return int(M) <= 65536

def choose_phase_dtype(M: int, prefer_float32: bool, allow_downgrade: bool) -> Tuple[np.dtype, bool]:
    """
    Decide phase dtype for θ materialization.
    Returns (dtype, precision_safe), where precision_safe indicates whether
    the chosen dtype is considered safe (i.e., guarantees correct round-trip).
    """
    if prefer_float32 and is_float32_safe_for_M(M):
        return (np.float32, True)
    if prefer_float32 and not allow_downgrade:
        # User insists on float32 even if not in conservative safe zone.
        return (np.float32, False)
    return (np.float64, True)


# ---------- Phases ----------

def wrap_phase(theta: np.ndarray, dtype: np.dtype = np.float64) -> np.ndarray:
    """
    Wrap phases into [0, 2π) using requested dtype (default float64).
    """
    th = np.asarray(theta, dtype=dtype)
    th = np.mod(th, TWO_PI, dtype=dtype)
    # Use float64 for the isclose comparison thresholding to stabilize edge case ~2π
    mask = np.isclose(th.astype(np.float64), TWO_PI)
    if np.any(mask):
        th = th.copy()
        th[mask] = dtype.type(0.0) if hasattr(dtype, "type") else dtype(0.0)
    return th

def nearest_phase_indices(theta: np.ndarray, M: int) -> np.ndarray:
    """
    Convert phases back to lattice indices {0..M-1} using nearest node.
    Decode is performed in float64 domain for numerical stability.
    """
    th = wrap_phase(theta, dtype=np.float64)
    n = np.rint(M * th / TWO_PI).astype(np.int64) % M
    return n

def grid_phases_from_uint(x_uint: np.ndarray, M: int, dtype: np.dtype = np.float64) -> np.ndarray:
    """
    Convert discrete symbols {0..M-1} to phase lattice nodes in requested dtype.
    """
    n = np.asarray(x_uint, dtype=np.int64) % M
    return (TWO_PI * n / M).astype(dtype)


# ---------- Binary packing helpers (msgpack/cbor compatible) ----------

def pack_ndarray(arr: np.ndarray, *, for_json: bool = False) -> Dict[str, Any]:
    """
    Pack a NumPy array into a JSON/msgpack/cbor-friendly dict.

    For binary formats (msgpack/cbor):
        {'__nd__': True, 'dtype': 'float32', 'shape': (N,...), 'data': <bytes>}
    For JSON (optional):
        {'__nd__': True, 'dtype': 'float32', 'shape': (N,...), 'data_b64': <base64 str>}
    """
    obj: Dict[str, Any] = {
        "__nd__": True,
        "dtype": str(arr.dtype),
        "shape": tuple(arr.shape),
    }
    raw = np.ascontiguousarray(arr).tobytes()
    if for_json:
        import base64  # local import to avoid mandatory dependency
        obj["data_b64"] = base64.b64encode(raw).decode("ascii")
    else:
        obj["data"] = raw
    return obj

def unpack_ndarray(obj: Dict[str, Any]) -> np.ndarray:
    """
    Unpack a dict produced by pack_ndarray() back into a NumPy array.
    Supports both 'data' (bytes) and 'data_b64' (base64 string) payloads.
    """
    if not isinstance(obj, dict) or obj.get("__nd__") is not True:
        raise TypeError("unpack_ndarray expects a packed ndarray object")
    dt = np.dtype(obj["dtype"])
    shape = tuple(obj["shape"])
    if "data" in obj:
        buf = obj["data"]
        if not isinstance(buf, (bytes, bytearray)):
            raise TypeError("packed ndarray 'data' must be bytes")
    elif "data_b64" in obj:
        import base64
        buf = base64.b64decode(obj["data_b64"])
    else:
        raise KeyError("packed ndarray missing 'data' or 'data_b64'")
    arr = np.frombuffer(buf, dtype=dt)
    try:
        arr = arr.reshape(shape)
    except Exception as e:
        raise ValueError(f"cannot reshape unpacked ndarray to {shape}: {e}")
    return arr


# ---------- Optional dependency checks ----------

def check_msgpack_available() -> bool:
    """Return True if 'msgpack' is importable in the current environment."""
    try:
        import msgpack  # noqa: F401
        return True
    except Exception:
        return False

def check_cbor_available() -> bool:
    """Return True if 'cbor2' is importable in the current environment."""
    try:
        import cbor2  # noqa: F401
        return True
    except Exception:
        return False


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
