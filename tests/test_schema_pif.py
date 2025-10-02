# tests/test_schema_pif.py
import os, sys, json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

import numpy as np
import pytest

from phasebridge.codec_s1 import S1PhaseCodec
from phasebridge.schema import get_default_schema, validate_pif_dict


def _mk_valid_pif_dict(N=1024, M=256):
    codec = S1PhaseCodec(M=M)
    x = np.arange(N, dtype=codec._min_uint_dtype(M)) % M
    schema = {"alphabet": {"type": "uint", "M": M}, "sampling": {"fs": 100.0}}
    p = codec.encode(x, schema)
    return {
        "schema": p.schema,
        "theta": p.theta.tolist(),
        "amp": p.amp,
        "meta": p.meta,
        "codec": {"forward": p.meta.get("codec"), "inverse": p.meta.get("codec")}
    }

def test_validate_ok_default_schema():
    s = get_default_schema()
    obj = _mk_valid_pif_dict()
    validate_pif_dict(obj, schema=s, use_jsonschema=False, also_runtime_validate=True)

def test_bad_note_fails():
    s = get_default_schema()
    obj = _mk_valid_pif_dict()
    obj["meta"]["note"] = "invalid"
    with pytest.raises(ValueError):
        validate_pif_dict(obj, schema=s, use_jsonschema=False, also_runtime_validate=True)

def test_bad_alphabet_type_fails():
    s = get_default_schema()
    obj = _mk_valid_pif_dict()
    obj["schema"]["alphabet"]["type"] = "float"
    with pytest.raises(ValueError):
        validate_pif_dict(obj, schema=s, use_jsonschema=False, also_runtime_validate=True)

def test_bad_M_range_fails():
    s = get_default_schema()
    obj = _mk_valid_pif_dict()
    obj["schema"]["alphabet"]["M"] = 1
    with pytest.raises(ValueError):
        validate_pif_dict(obj, schema=s, use_jsonschema=False, also_runtime_validate=True)

def test_bad_sampling_fs_fails():
    s = get_default_schema()
    obj = _mk_valid_pif_dict()
    obj["schema"]["sampling"]["fs"] = -10.0
    with pytest.raises(ValueError):
        validate_pif_dict(obj, schema=s, use_jsonschema=False, also_runtime_validate=True)
