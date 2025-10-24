# cli/pb_validate.py
from __future__ import annotations
import argparse, sys, json
from pathlib import Path
import numpy as np

from phasebridge.pif import PIF
from phasebridge.codec_s1 import S1PhaseCodec
from phasebridge.schema import validate_pif_dict, validate_pif_json
from phasebridge.utils import sha256_of_array

def _detect_pif_fmt(path: Path | None, explicit: str | None) -> str:
    if explicit:
        return explicit
    if path is None:
        return "json"  # stdin
    suf = path.suffix.lower()
    if suf in (".mp", ".msgpack", ".mpk"):
        return "msgpack"
    if suf in (".cbor", ".cbor2"):
        return "cbor"
    if suf == ".npz":
        return "npz"
    return "json"

def _load_pif(path: Path | None, pif_fmt: str, raw_bytes: bytes | None = None) -> dict | PIF:
    if pif_fmt == "json":
        if raw_bytes is None:
            assert path is not None
            txt = path.read_text(encoding="utf-8")
            # validate schema + runtime in one go
            validate_pif_json(txt, use_jsonschema=False, also_runtime_validate=True)
            return PIF.from_json(txt, validate=True)
        else:
            s = raw_bytes.decode("utf-8")
            validate_pif_json(s, use_jsonschema=False, also_runtime_validate=True)
            return PIF.from_json(s, validate=True)
    else:
        # binary formats (msgpack/cbor/npz)
        if raw_bytes is None:
            assert path is not None
            raw_bytes = path.read_bytes()
        # use unified binary loader with ndarray-unpacking inside
        return PIF.from_bytes(raw_bytes, fmt=pif_fmt, validate=True)

def _load_raw_file(path: Path, in_fmt: str, dtype: np.dtype) -> np.ndarray:
    in_fmt = in_fmt.lower()
    if in_fmt == "npy":
        arr = np.load(path)
        if isinstance(arr, np.lib.npyio.NpzFile):
            raise ValueError("Use a single .npy array for --in-fmt=npy")
        return np.asarray(arr, dtype=dtype)
    elif in_fmt == "csv":
        return np.loadtxt(path, delimiter=",").astype(dtype)
    elif in_fmt == "bin":
        return np.fromfile(path, dtype=dtype)
    else:
        raise ValueError(f"Unsupported --in-fmt: {in_fmt}")

def main():
    ap = argparse.ArgumentParser(
        description="Validate PIF: schema/runtime, decode, hash check, raw match (optional)"
    )
    ap.add_argument("--in", dest="inp", default="-", help="input PIF file or '-' for stdin")
    ap.add_argument("--pif-fmt", choices=["json","msgpack","cbor","npz"], default=None, help="PIF format (auto)")
    ap.add_argument("--raw", dest="raw", default=None, help="optional raw file to compare with decoded")
    ap.add_argument("--in-fmt", dest="in_fmt", choices=["bin","csv","npy"], default="bin",
                    help="raw input format (if --raw is given)")
    ap.add_argument("--dtype", dest="dtype", default="uint8", help="raw dtype (if --raw is given)")
    ap.add_argument("--report", choices=["json","text"], default="json", help="report format (default json)")
    args = ap.parse_args()

    # read PIF
    if args.inp == "-" or not args.inp.strip():
        b = sys.stdin.buffer.read()
        in_path = None
    else:
        in_path = Path(args.inp)
        if not in_path.exists():
            ap.error(f"Input file not found: {in_path}")
        b = None

    pif_fmt = _detect_pif_fmt(in_path, args.pif_fmt)
    try:
        p = _load_pif(in_path, pif_fmt, raw_bytes=b)
    except Exception as e:
        report = {"ok": False, "error": f"PIF validation failed: {e}"}
        print(json.dumps(report, ensure_ascii=False, indent=2))
        sys.exit(1)

    # decode
    try:
        M = int(p.schema["alphabet"]["M"])
    except Exception:
        report = {"ok": False, "error": "PIF schema.alphabet.M missing or invalid"}
        print(json.dumps(report, ensure_ascii=False, indent=2))
        sys.exit(1)

    codec = S1PhaseCodec(M=M)
    x_dec = codec.decode(p)

    # compute hash of decoded and compare with meta.hash_raw (if present)
    meta_hash = p.meta.get("hash_raw")
    decoded_hash = sha256_of_array(x_dec)
    hash_match = (meta_hash is None) or (meta_hash == decoded_hash)

    raw_match = None
    raw_hash_match = None
    if args.raw:
        raw_path = Path(args.raw)
        if not raw_path.exists():
            ap.error(f"Raw file not found: {raw_path}")
        dtype = np.dtype(args.dtype)
        x_raw = _load_raw_file(raw_path, args.in_fmt, dtype)

        # compare equality
        raw_match = bool(np.array_equal(x_raw, x_dec))
        # compare hashes vs meta.hash_raw (if present)
        if meta_hash is not None:
            raw_hash_match = (sha256_of_array(x_raw) == meta_hash)

    ok = True and hash_match and (raw_match is not False)
    checks = {
        "schema_runtime_ok": True,       # schema + runtime validation passed
        "decode_ok": True,               # decode step passed
        "hash_match": bool(hash_match),
        "raw_match": None if raw_match is None else bool(raw_match),
        "raw_hash_match": None if raw_hash_match is None else bool(raw_hash_match),
        "note": p.meta.get("note", None),
    }
    report = {
        "ok": bool(ok),
        "M": M,
        "N": int(x_dec.size),
        "checks": checks,
        "meta": {
            "hash_raw": meta_hash,
            "codec": p.meta.get("codec"),
            "codec_hash": p.meta.get("codec_hash"),
            "note": p.meta.get("note"),
        }
    }

    if args.report == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        # text
        print(f"OK: {report['ok']}")
        for k, v in checks.items():
            print(f" - {k}: {v}")
        print(f"M={M}, N={x_dec.size}")
        if meta_hash:
            print(f"hash_raw: {meta_hash}")
        if p.meta.get("codec"):
            print(f"codec: {p.meta['codec']}")

    sys.exit(0 if report["ok"] else 1)

if __name__ == "__main__":
    main()
