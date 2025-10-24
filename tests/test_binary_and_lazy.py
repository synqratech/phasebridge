# tests/test_binary_and_lazy.py
import numpy as np
import pytest

from phasebridge.codec_s1 import S1PhaseCodec
from phasebridge.pif import PIF


def _mk_schema(M: int):
    return {"alphabet": {"type": "uint", "M": int(M)}}


@pytest.mark.parametrize("fmt", ["msgpack", "cbor", "npz"])
def test_lazy_roundtrip_binary_formats(fmt):
    M = 256
    rng = np.random.default_rng(0)
    x = rng.integers(0, M, size=10_000, dtype=np.uint8)

    codec = S1PhaseCodec(M=M, strict_range=True)
    p = codec.encode(
        x, schema=_mk_schema(M),
        lazy_theta=True,
        prefer_float32=True,      # safe for M<=65536
        allow_downgrade=True
    )
    assert getattr(p, "theta_lazy", False) is True

    blob = p.to_bytes(fmt=fmt)
    p2 = PIF.from_bytes(blob, fmt=fmt, validate=True)
    xr = codec.decode(p2)
    assert np.array_equal(x, xr)

    # materialization dtype hint should be respected (float32)
    th = p2.theta_view
    assert th.dtype in (np.float32, np.float64)  # float32 preferred; npz path may normalize


def test_eager_float32_policy_safe():
    M = 65536  # conservative safe bound
    x = np.arange(0, M, dtype=np.uint16)
    codec = S1PhaseCodec(M=M, strict_range=True)
    p = codec.encode(
        x, schema=_mk_schema(M),
        lazy_theta=False,
        prefer_float32=True,
        allow_downgrade=True
    )
    # numeric hints must reflect dtype choice
    assert p.numeric is not None
    assert p.numeric.get("dtype") in ("float32", "float64")
    assert p.numeric.get("precision_safe") is True
    xr = codec.decode(p)
    assert np.array_equal(x, xr)


def test_eager_float32_policy_unsafe_no_downgrade_discloses_risk():
    M = 100_000  # above safe bound -> unsafe if forced float32
    rng = np.random.default_rng(1)
    x = rng.integers(0, M, size=4096, dtype=np.uint32)
    codec = S1PhaseCodec(M=M, strict_range=True)
    p = codec.encode(
        x, schema=_mk_schema(M),
        lazy_theta=False,
        prefer_float32=True,
        allow_downgrade=False
    )
    # We only check that the risk is flagged; round-trip is not guaranteed in this mode.
    assert p.numeric is not None
    assert p.numeric.get("dtype") == "float32"
    assert p.numeric.get("precision_safe") is False


def test_npz_roundtrip_eager_and_lazy():
    M = 1024
    x = np.arange(0, 10_000, dtype=np.uint16) % M
    codec = S1PhaseCodec(M=M)

    # eager
    p = codec.encode(x, schema=_mk_schema(M), lazy_theta=False)
    b = p.to_bytes(fmt="npz")
    p2 = PIF.from_bytes(b, fmt="npz", validate=True)
    assert np.array_equal(codec.decode(p2), x)

    # lazy
    pL = codec.encode(x, schema=_mk_schema(M), lazy_theta=True)
    bL = pL.to_bytes(fmt="npz")
    pL2 = PIF.from_bytes(bL, fmt="npz", validate=True)
    assert getattr(pL2, "theta_lazy", False) is True
    assert np.array_equal(codec.decode(pL2), x)
