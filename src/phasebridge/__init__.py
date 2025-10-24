# src/phasebridge/__init__.py
from .pif import PIF, validate_pif
from .codec_s1 import S1PhaseCodec
from .kappa import kappa_timeseries, kappa_timeseries_windowed
from .utils import (
    sha256_bytes,
    prefixed_sha256_bytes,
    sha256_of_array,
    is_uint_array,
    is_float64_array,
    min_uint_dtype,
    as_uint_array,
    choose_phase_dtype,
    is_float32_safe_for_M,
    wrap_phase,
    nearest_phase_indices,
    grid_phases_from_uint,
    safe_len,
    verify_roundtrip,
)
from .errors import (
    PhaseBridgeError,
    SchemaError,
    SchemaValidationError,
    IncompatibleSchemaError,
    CodecError,
    PhaseFormatError,
    RoundTripError,
    KappaError,
    NotSupportedError,
)

__all__ = [
    # Core
    "PIF", "validate_pif",
    "S1PhaseCodec",
    # Kappa
    "kappa_timeseries", "kappa_timeseries_windowed",
    # Utils
    "sha256_bytes", "prefixed_sha256_bytes", "sha256_of_array",
    "is_uint_array", "is_float64_array", "min_uint_dtype", "as_uint_array",
    "choose_phase_dtype", "is_float32_safe_for_M",
    "wrap_phase", "nearest_phase_indices", "grid_phases_from_uint",
    "safe_len", "verify_roundtrip",
    # Errors
    "PhaseBridgeError", "SchemaError", "SchemaValidationError", "IncompatibleSchemaError",
    "CodecError", "PhaseFormatError", "RoundTripError", "KappaError", "NotSupportedError",
]
