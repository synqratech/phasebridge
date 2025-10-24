# src/phasebridge/pif.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Union, Optional
import numpy as np
import json
import re
import io
import zipfile

from .utils import grid_phases_from_uint, pack_ndarray, unpack_ndarray  # lazy θ + binary packing
from .errors import SerializationError, UnsupportedFormatError

TWO_PI = 2.0 * np.pi


def _wrap_phase(theta: np.ndarray, dtype: np.dtype = np.float64) -> np.ndarray:
    """Wrap phases to [0, 2π) using requested dtype (default float64)."""
    th = np.asarray(theta, dtype=dtype)
    th = np.mod(th, TWO_PI, dtype=dtype)
    # Stabilize ~2π edge using float64 comparison
    mask = np.isclose(th.astype(np.float64), TWO_PI)
    if np.any(mask):
        th = th.copy()
        th[mask] = dtype.type(0.0) if hasattr(dtype, "type") else dtype(0.0)
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
    if not (isinstance(M, int) and 2 <= M <= (1 << 32)):
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
        if not (isinstance(hr, str) and hr.startswith("sha256:") and len(hr) >= len("sha256:") + 64):
            raise ValueError("meta.hash_raw must be 'sha256:<64 hex chars>' if provided")
        hx = hr.split(":", 1)[1]
        if not re.fullmatch(r"[0-9a-fA-F]{64}", hx):
            raise ValueError("meta.hash_raw hex invalid")
    ch = meta.get("codec_hash", None)
    if ch is not None:
        if not (isinstance(ch, str) and ch.startswith("sha256:") and len(ch) >= len("sha256:") + 64):
            raise ValueError("meta.codec_hash must be 'sha256:<64 hex chars>' if provided")
        hx = ch.split(":", 1)[1]
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

    Normal mode:
      - theta: float64 array of shape (N,), phases wrapped to [0, 2π).
    Lazy mode:
      - encoded_uint: uint array of shape (N,) with symbols {0..M-1},
        theta_lazy=True, theta is materialized on first access via grid mapping.

    - amp: float or float64 array; MVP uses 1.0 (scalar).
    - numeric: optional dict, may include {"dtype": "float32" | "float64", "precision_safe": bool}
    - schema: dict with at least {alphabet: {type: "uint", M: int}} and optional sampling.fs
    - meta: dict with at least note: "no_processing" in MVP.
    """
    schema: Dict[str, Any]
    theta: Optional[np.ndarray] = None
    amp: Union[float, np.ndarray] = 1.0
    meta: Dict[str, Any] = None
    numeric: Optional[Dict[str, Any]] = None

    # Lazy-θ additions
    encoded_uint: Optional[np.ndarray] = None
    theta_lazy: bool = False
    _theta_cache: Optional[np.ndarray] = None  # materialized θ cache (lazy mode)

    # ----- Properties -----
    @property
    def M(self) -> int:
        return int(self.schema["alphabet"]["M"])

    @property
    def theta_view(self) -> np.ndarray:
        """
        Access θ. In lazy mode, materializes θ = 2π * n / M on first access.
        """
        if self.theta_lazy:
            if self._theta_cache is not None:
                return self._theta_cache
            if self.encoded_uint is None:
                raise ValueError("theta_lazy=True but encoded_uint is missing")
            # Materialize and cache
            mat_dtype = np.float32 if (self.numeric and self.numeric.get("dtype") == "float32") else np.float64
            self._theta_cache = grid_phases_from_uint(self.encoded_uint, self.M, dtype=mat_dtype)
            return self._theta_cache
        # Normal mode
        if self.theta is None:
            raise ValueError("theta is not available")
        return self.theta

    # ----- Dataclass lifecycle -----
    def __post_init__(self):
        # amp normalization
        if isinstance(self.amp, np.ndarray):
            if self.amp.dtype != np.float64:
                self.amp = self.amp.astype(np.float64)
        else:
            self.amp = float(self.amp)

        # meta default
        if self.meta is None:
            self.meta = {"note": "no_processing"}

        # phase normalization
        if self.theta_lazy:
            # lazy mode: do not wrap theta; theta may be None
            # ensure encoded_uint (if provided) is contiguous uint array
            if self.encoded_uint is not None:
                enc = np.asarray(self.encoded_uint)
                if not np.issubdtype(enc.dtype, np.unsignedinteger):
                    raise ValueError("encoded_uint must be an unsigned integer array")
                self.encoded_uint = np.ascontiguousarray(enc)
        else:
            # normal mode: require theta and wrap
            if self.theta is None:
                raise ValueError("theta must be provided in non-lazy mode")
            desired_dtype = np.float32 if (self.numeric and self.numeric.get("dtype") == "float32") else np.float64
            self.theta = _wrap_phase(np.asarray(self.theta, dtype=desired_dtype), dtype=desired_dtype)

        # amp-shape consistency (without forcing materialization):
        if isinstance(self.amp, np.ndarray):
            if self.theta_lazy:
                if self.encoded_uint is None:
                    raise ValueError("theta_lazy=True requires encoded_uint for amp shape check")
                if self.amp.shape != self.encoded_uint.shape:
                    raise ValueError("amp array shape must match encoded_uint shape in lazy mode")
            else:
                if self.theta is None:
                    raise ValueError("theta is required to validate amp shape")
                if self.amp.shape != self.theta.shape:
                    raise ValueError("amp array shape must match theta shape")

    # ----- Serialization -----
    def to_dict(self) -> Dict[str, Any]:
        obj: Dict[str, Any] = {
            "schema": self.schema,
            "amp": self.amp if not isinstance(self.amp, np.ndarray) else self.amp.astype(np.float64).tolist(),
            "meta": self.meta,
        }
        if self.numeric is not None:
            obj["numeric"] = self.numeric
        if self.theta_lazy:
            obj["theta_lazy"] = True
            if self.encoded_uint is None:
                raise ValueError("theta_lazy=True but encoded_uint is missing for serialization")
            obj["encoded_uint"] = np.asarray(self.encoded_uint).astype(int).tolist()
        else:
            if self.theta is None:
                raise ValueError("theta is missing for serialization")
            # Serialize θ in its current dtype
            if self.theta.dtype == np.float32:
                obj["theta"] = self.theta.astype(np.float32).tolist()
            else:
                obj["theta"] = self.theta.astype(np.float64).tolist()
        return obj

    def to_json(self, indent: Optional[int] = 0) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent if indent is not None else 0)

    # ----- Deserialization -----
    @staticmethod
    def from_dict(d: Dict[str, Any], validate: bool = True) -> "PIF":
        schema = d["schema"]

        # amp parsing
        amp_val = d.get("amp", 1.0)
        amp = np.asarray(amp_val, dtype=np.float64) if isinstance(amp_val, list) else float(amp_val)

        # meta parsing
        meta = d.get("meta", {"note": "no_processing"})
        numeric = d.get("numeric", None)

        # lazy branch
        if d.get("theta_lazy", False) and "encoded_uint" in d:
            enc = np.asarray(d["encoded_uint"])
            # choose an unsigned dtype that can hold values (we don't know minimal a priori)
            if not np.issubdtype(enc.dtype, np.unsignedinteger):
                # try cast from Python ints
                enc = enc.astype(np.uint64, copy=False)
            p = PIF(
                schema=schema,
                theta=None,
                amp=amp,
                meta=meta,
                numeric=numeric,
                encoded_uint=enc,
                theta_lazy=True,
                _theta_cache=None,
            )
        else:
            # normal branch expects theta
            # Respect numeric.dtype if provided
            desired_dtype = np.float32 if (numeric and numeric.get("dtype") == "float32") else np.float64
            theta = np.asarray(d["theta"], dtype=desired_dtype)
            p = PIF(
                schema=schema,
                theta=theta,
                amp=amp,
                meta=meta,
                numeric=numeric,
                encoded_uint=None,
                theta_lazy=False,
                _theta_cache=None,
            )

        if validate:
            validate_pif(p)
        return p

    @staticmethod
    def from_json(s: str, validate: bool = True) -> "PIF":
        d = json.loads(s)
        return PIF.from_dict(d, validate=validate)

    # ===== Binary Serialization API =====
    def _to_obj(self) -> Dict[str, Any]:
        """
        Internal: produce a dict with NumPy arrays preserved (no list conversion).
        Structure (lazy/eager aware):
          {
            "schema": dict, "meta": dict, "numeric": dict|None,
            "theta_lazy": bool,
            "theta": np.ndarray (if not lazy)  OR
            "encoded_uint": np.ndarray (if lazy),
            "amp": float | np.ndarray
          }
        """
        obj: Dict[str, Any] = {
            "schema": self.schema,
           "meta": self.meta,
            "numeric": self.numeric if self.numeric is not None else None,
            "theta_lazy": bool(self.theta_lazy),
        }
        # amp as scalar or ndarray
        if isinstance(self.amp, np.ndarray):
            obj["amp"] = np.asarray(self.amp)  # keep ndarray
        else:
            obj["amp"] = float(self.amp)

        if self.theta_lazy:
            if self.encoded_uint is None:
                raise SerializationError("theta_lazy=True but encoded_uint is missing for serialization")
            obj["encoded_uint"] = np.asarray(self.encoded_uint)
        else:
            if self.theta is None:
                raise SerializationError("theta is missing for serialization")
            obj["theta"] = np.asarray(self.theta)
        return obj

    @staticmethod
    def _from_obj(obj: Dict[str, Any], validate: bool) -> "PIF":
        """
        Internal: consume dict produced by _to_obj() (NumPy arrays allowed) and
        create a PIF via from_dict-compatible structure.
        """
        d: Dict[str, Any] = {
           "schema": obj["schema"],
            "meta": obj.get("meta", {"note": "no_processing"}),
        }
        if obj.get("numeric") is not None:
            d["numeric"] = obj["numeric"]
        # amp: keep scalar or turn ndarray -> list for from_dict
        amp = obj.get("amp", 1.0)
        if isinstance(amp, np.ndarray):
            d["amp"] = amp  # from_dict accepts ndarray as list; it casts anyway
        else:
            d["amp"] = float(amp)

        if obj.get("theta_lazy", False):
            d["theta_lazy"] = True
            enc = obj.get("encoded_uint", None)
            if enc is None:
                raise SerializationError("theta_lazy=True but 'encoded_uint' missing in payload")
            d["encoded_uint"] = enc
        else:
            theta = obj.get("theta", None)
            if theta is None:
                raise SerializationError("'theta' missing in eager-θ payload")
            d["theta"] = theta

        return PIF.from_dict(d, validate=validate)

    @staticmethod
    def _transform_pack(x: Any, *, for_json: bool = False) -> Any:
        """Recursively pack NumPy arrays into {__nd__, dtype, shape, data} dicts."""
        if isinstance(x, np.ndarray):
            return pack_ndarray(x, for_json=for_json)
        if isinstance(x, dict):
            return {k: PIF._transform_pack(v, for_json=for_json) for k, v in x.items()}
        if isinstance(x, (list, tuple)):
            return [PIF._transform_pack(v, for_json=for_json) for v in x]
        return x

    @staticmethod
    def _transform_unpack(x: Any) -> Any:
        """Recursively unpack {__nd__...} dicts back into NumPy arrays."""
        if isinstance(x, dict) and x.get("__nd__") is True:
            return unpack_ndarray(x)
        if isinstance(x, dict):
            return {k: PIF._transform_unpack(v) for k, v in x.items()}
        if isinstance(x, list):
            return [PIF._transform_unpack(v) for v in x]
        return x

    def to_bytes(self, fmt: str = "msgpack") -> bytes:
        """
        Serialize PIF to binary.
        Supported fmt: "msgpack", "cbor", "npz".
        """
        obj = self._to_obj()

        if fmt == "msgpack":
            try:
                import msgpack  # type: ignore
            except Exception as e:
                raise SerializationError("msgpack not available") from e
            packed = self._transform_pack(obj, for_json=False)
            return msgpack.dumps(packed, use_bin_type=True)

        if fmt == "cbor":
            try:
                import cbor2  # type: ignore
            except Exception as e:
                raise SerializationError("cbor2 not available") from e
            packed = self._transform_pack(obj, for_json=False)
            return cbor2.dumps(packed)

        if fmt == "npz":
            # Zip layout:
            #  schema.json, meta.json, numeric.json (optional), flags.json
            #  theta.npy or encoded_uint.npy
            #  amp.npy (if array) or amp.json (if scalar)
            bio = io.BytesIO()
            with zipfile.ZipFile(bio, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
                # JSON helpers
                def _wjson(name: str, data: Dict[str, Any]) -> None:
                    zf.writestr(name, json.dumps(data, ensure_ascii=False, separators=(",", ":")))

                _wjson("schema.json", obj["schema"])
                _wjson("meta.json", obj.get("meta", {"note": "no_processing"}))
                if obj.get("numeric") is not None:
                    _wjson("numeric.json", obj["numeric"])
                _wjson("flags.json", {"theta_lazy": bool(obj.get("theta_lazy", False))})

                # Arrays
                if obj.get("theta_lazy", False):
                    enc = obj.get("encoded_uint", None)
                    if enc is None:
                        raise SerializationError("npz: theta_lazy=True but 'encoded_uint' missing")
                    buf = io.BytesIO()
                    np.save(buf, np.asarray(enc), allow_pickle=False)
                    zf.writestr("encoded_uint.npy", buf.getvalue())
                else:
                    th = obj.get("theta", None)
                    if th is None:
                        raise SerializationError("npz: eager-θ but 'theta' missing")
                    buf = io.BytesIO()
                    np.save(buf, np.asarray(th), allow_pickle=False)
                    zf.writestr("theta.npy", buf.getvalue())

                # amp
                amp = obj.get("amp", 1.0)
                if isinstance(amp, np.ndarray):
                    buf = io.BytesIO()
                    np.save(buf, np.asarray(amp), allow_pickle=False)
                    zf.writestr("amp.npy", buf.getvalue())
                else:
                    _wjson("amp.json", {"scalar": float(amp)})

            return bio.getvalue()

        raise UnsupportedFormatError(f"Unknown format: {fmt}")

    @staticmethod
    def from_bytes(data: bytes, fmt: str = "msgpack", validate: bool = True) -> "PIF":
        """
        Deserialize PIF from binary.
        Supported fmt: "msgpack", "cbor", "npz".
        """
        if fmt == "msgpack":
            try:
                import msgpack  # type: ignore
            except Exception as e:
                raise SerializationError("msgpack not available") from e
            try:
                obj2 = msgpack.loads(data, raw=False)
                obj = PIF._transform_unpack(obj2)
            except Exception as e:
                raise SerializationError("failed to decode msgpack payload") from e
            return PIF._from_obj(obj, validate=validate)

        if fmt == "cbor":
            try:
                import cbor2  # type: ignore
            except Exception as e:
                raise SerializationError("cbor2 not available") from e
            try:
                obj2 = cbor2.loads(data)
                obj = PIF._transform_unpack(obj2)
            except Exception as e:
                raise SerializationError("failed to decode cbor payload") from e
            return PIF._from_obj(obj, validate=validate)

        if fmt == "npz":
            try:
                bio = io.BytesIO(data)
                with zipfile.ZipFile(bio, mode="r") as zf:
                    def _rjson(name: str, required: bool = True) -> Optional[Dict[str, Any]]:
                        try:
                            with zf.open(name, "r") as fh:
                                return json.loads(fh.read().decode("utf-8"))
                        except KeyError:
                            if required:
                                raise SerializationError(f"npz: missing {name}")
                            return None

                    schema = _rjson("schema.json")
                    meta = _rjson("meta.json")
                    numeric = _rjson("numeric.json", required=False)
                    flags = _rjson("flags.json")
                    theta_lazy = bool(flags.get("theta_lazy", False)) if flags else False

                    # Arrays
                    theta = None
                    encoded_uint = None
                    try:
                        if theta_lazy:
                            with zf.open("encoded_uint.npy", "r") as fh:
                                encoded_uint = np.load(io.BytesIO(fh.read()), allow_pickle=False)
                        else:
                            with zf.open("theta.npy", "r") as fh:
                                theta = np.load(io.BytesIO(fh.read()), allow_pickle=False)
                    except KeyError as e:
                        raise SerializationError("npz: required ndarray missing") from e

                    # amp
                    amp: Union[float, np.ndarray]
                    if "amp.npy" in zf.namelist():
                        with zf.open("amp.npy", "r") as fh:
                            amp = np.load(io.BytesIO(fh.read()), allow_pickle=False)
                    else:
                        amp_json = _rjson("amp.json", required=False) or {"scalar": 1.0}
                        amp = float(amp_json.get("scalar", 1.0))

                obj: Dict[str, Any] = {
                    "schema": schema,
                    "meta": meta,
                    "numeric": numeric,
                    "theta_lazy": theta_lazy,
                    "amp": amp,
                }
                if theta_lazy:
                    obj["encoded_uint"] = encoded_uint
                else:
                    obj["theta"] = theta

            except SerializationError:
                raise
            except Exception as e:
                raise SerializationError("failed to decode npz payload") from e

            return PIF._from_obj(obj, validate=validate)

        raise UnsupportedFormatError(f"Unknown format: {fmt}")

def validate_pif(p: PIF) -> None:
    """Validate PIF object against minimal v1 core constraints (lazy-aware)."""
    _validate_schema_dict(p.schema)

    # Validate amp (type + nonnegativity); shape checked in __post_init__
    if isinstance(p.amp, np.ndarray):
        if not _dtype_is_float64(p.amp):
            raise ValueError("amp array must be float64")
        if np.any(~np.isfinite(p.amp)):
            raise ValueError("amp must be finite")
        if np.any(p.amp < 0):
            raise ValueError("amp must be non-negative")
    else:
        if not isinstance(p.amp, float):
            raise ValueError("amp scalar must be float")
        if not np.isfinite(p.amp):
            raise ValueError("amp must be finite")
        if p.amp < 0.0:
            raise ValueError("amp must be non-negative")

    # Meta
    _validate_meta_dict(p.meta)

    # Phase / symbols (lazy-aware)
    if p.theta_lazy:
        # encoded_uint must exist, be unsigned, 1-D, and finite shape
        if p.encoded_uint is None:
            raise ValueError("theta_lazy=True requires encoded_uint")
        enc = np.asarray(p.encoded_uint)
        if enc.ndim != 1:
            raise ValueError("encoded_uint must be a 1-D array")
        if not np.issubdtype(enc.dtype, np.unsignedinteger):
            raise ValueError("encoded_uint must be an unsigned integer dtype")
        # No explicit range check here; codec strict mode enforces range by M
        # (optionally could enforce 0 <= enc < M)
    else:
        if p.theta is None:
            raise ValueError("theta must be provided in non-lazy mode")
        # Accept float32 or float64 θ
        if not (isinstance(p.theta, np.ndarray) and p.theta.dtype in (np.float32, np.float64)):
            raise ValueError("theta must be float32 or float64 array")
        if np.any(~np.isfinite(p.theta)):
            raise ValueError("theta must be finite")
        eps = np.finfo(p.theta.dtype).eps
        if np.any(p.theta < 0.0) or np.any(p.theta >= TWO_PI + eps):
            raise ValueError("theta must be in [0, 2π)")
        # If numeric dtype declared, enforce consistency in non-lazy mode
        if p.numeric and "dtype" in p.numeric:
            want = p.numeric["dtype"]
            if want == "float32" and p.theta.dtype != np.float32:
                raise ValueError("numeric.dtype=float32 but theta is not float32")
            if want == "float64" and p.theta.dtype != np.float64:
                raise ValueError("numeric.dtype=float64 but theta is not float64")
