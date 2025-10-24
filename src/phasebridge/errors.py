# src/phasebridge/errors.py
from __future__ import annotations


class PhaseBridgeError(Exception):
    """Base exception for the phasebridge library."""
    pass


# --- Schema / Validation ---
class SchemaError(PhaseBridgeError):
    """Schema format/content error."""
    pass


class SchemaValidationError(SchemaError):
    """PIF validation against schema failed."""
    pass


class IncompatibleSchemaError(SchemaError):
    """Schema incompatible with selected codec/parameters."""
    pass


# --- Codecs / Formats ---
class CodecError(PhaseBridgeError):
    """Codec error (encode/ decode)."""
    pass


class PhaseFormatError(PhaseBridgeError):
    """Invalid phase/amplitude format."""
    pass


class RoundTripError(PhaseBridgeError):
    """Round-trip contract violation (decode(encode(x)) != x)."""
    pass


# --- Kappa / Metrics ---
class KappaError(PhaseBridgeError):
    """Error computing coherence κ."""
    pass


# --- Lazy-θ / Access ---
class LazyPhaseError(PhaseBridgeError):
    """Accessed theta in lazy PIF without schema or M parameter."""
    pass


# --- Serialization / Transport ---
class SerializationError(PhaseBridgeError):
    """
    Binary serialization/deserialization error.

    Raised when:
      - required dependency is missing (e.g., msgpack/cbor2 not installed),
      - the binary payload is malformed or cannot be parsed,
      - underlying IO/packing/unpacking fails.
    """
    pass


class UnsupportedFormatError(PhaseBridgeError):
    """
    Unsupported serialization format.

    Raised when an unknown or unsupported `fmt` is requested, e.g. not in
    {'msgpack', 'cbor', 'npz'}.
    """
    pass


# --- Misc ---
class NotSupportedError(PhaseBridgeError):
    """Not yet supported (feature flag / roadmap)."""
    pass
