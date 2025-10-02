# tests/property/test_roundtrip_prop.py
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")))

import numpy as np
import pytest

try:
    from hypothesis import given, strategies as st
    _HAVE_HYP = True
except Exception:
    _HAVE_HYP = False

# If Hypothesis is unavailable or failed to import, skip this module cleanly
if not _HAVE_HYP:
    pytest.skip("hypothesis not installed", allow_module_level=True)


def _codec_and_data():
    from phasebridge.codec_s1 import S1PhaseCodec
    # Choose a random M and a dtype consistent with it
    M = st.sampled_from([2, 3, 7, 16, 31, 64, 127, 128, 255, 256, 1024, 65535, 65536])
    def mk_array(m):
        if m <= 256:
            dt = np.uint8
        elif m <= 65536:
            dt = np.uint16
        else:
            dt = np.uint32
        # length 0..2000
        n = st.integers(min_value=0, max_value=2000)
        arr = st.lists(st.integers(min_value=0, max_value=m-1), min_size=0, max_size=2000)
        return dt, n, arr

    return S1PhaseCodec, M, mk_array


@given(st.sampled_from([2, 3, 7, 16, 31, 64, 127, 128, 255, 256, 1024, 4096, 65535, 65536]),
       st.integers(min_value=0, max_value=2000),
       st.data())
def test_property_roundtrip(M, N, data):
    from phasebridge.codec_s1 import S1PhaseCodec
    dtype = np.uint8 if M <= 256 else (np.uint16 if M <= 65536 else np.uint32)

    # generate an array of length N with values [0..M-1]
    vals = data.draw(st.lists(st.integers(min_value=0, max_value=M-1), min_size=N, max_size=N))
    x = np.array(vals, dtype=dtype)

    codec = S1PhaseCodec(M=M, strict_range=True)
    schema = {"alphabet": {"type": "uint", "M": M}}
    p = codec.encode(x, schema)
    xr = codec.decode(p)
    assert np.array_equal(x, xr)
