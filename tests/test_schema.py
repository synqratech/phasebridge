# tests/test_schema.py
import json
import numpy as np
from phasebridge.schema import get_default_schema, validate_pif_dict
from phasebridge.codec_s1 import S1PhaseCodec

def _mk_pif_dict(N=1024, M=256):
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
    obj = _mk_pif_dict()
    validate_pif_dict(obj, schema=s, use_jsonschema=False, also_runtime_validate=True)

def test_validate_bad_note():
    s = get_default_schema()
    obj = _mk_pif_dict()
    obj["meta"]["note"] = "invalid_state"
    try:
        validate_pif_dict(obj, schema=s, use_jsonschema=False, also_runtime_validate=True)
        assert False, "must fail on invalid meta.note"
    except ValueError:
        pass

def test_validate_theta_type_fail():
    s = get_default_schema()
    obj = _mk_pif_dict()
    obj["theta"] = "not_an_array"
    try:
        validate_pif_dict(obj, schema=s, use_jsonschema=False, also_runtime_validate=True)
        assert False, "must fail on wrong theta type"
    except Exception:
        pass
