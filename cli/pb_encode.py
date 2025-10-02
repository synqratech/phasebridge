# cli/pb_encode.py
from __future__ import annotations
import argparse
import sys
import json
from pathlib import Path
from typing import Optional
import numpy as np

try:
    import msgpack  # optional
    _HAVE_MSGPACK = True
except Exception:
    msgpack = None  # type: ignore
    _HAVE_MSGPACK = False

from phasebridge.codec_s1 import S1PhaseCodec
from phasebridge.pif import PIF

def _load_raw_from_file(path: Path, in_fmt: str, dtype: np.dtype) -> np.ndarray:
    in_fmt = in_fmt.lower()
    if in_fmt == "npy":
        arr = np.load(path)
        if isinstance(arr, np.lib.npyio.NpzFile):
            raise ValueError("Use .npy (single array) for --in-fmt=npy in MVP.")
        return np.asarray(arr, dtype=dtype)
    elif in_fmt == "csv":
        return np.loadtxt(path, delimiter=",").astype(dtype)
    elif in_fmt == "bin":
        return np.fromfile(path, dtype=dtype)
    else:
        raise ValueError(f"Unsupported --in-fmt: {in_fmt}")

def _load_raw_from_stdin(in_fmt: str, dtype: np.dtype) -> np.ndarray:
    in_fmt = in_fmt.lower()
    buf = sys.stdin.buffer.read()
    if in_fmt == "bin":
        if len(buf) % np.dtype(dtype).itemsize != 0:
            raise ValueError("stdin byte length is not a multiple of dtype size")
        return np.frombuffer(buf, dtype=dtype)
    elif in_fmt == "csv":
        # Decode text and parse CSV quickly
        txt = buf.decode("utf-8")
        return np.loadtxt(txt.splitlines(), delimiter=",").astype(dtype)
    else:
        raise ValueError("stdin supported only for --in-fmt=bin|csv in MVP")

def _serialize_pif_json(p: PIF, pretty: bool) -> bytes:
    s = p.to_json(indent=2 if pretty else 0)
    return s.encode("utf-8")

def _serialize_pif_msgpack(p: PIF) -> bytes:
    if not _HAVE_MSGPACK:
        raise RuntimeError("msgpack not installed. pip install msgpack")
    obj = p.to_dict()
    return msgpack.packb(obj, use_bin_type=True)  # type: ignore

def main():
    ap = argparse.ArgumentParser(
        description="PIF encoder (strict lossless): raw (bin/csv/npy) -> PIF (json/msgpack)"
    )
    ap.add_argument("--in", dest="inp", default="-", help="input file path or '-' for stdin")
    ap.add_argument("--in-fmt", dest="in_fmt", choices=["bin","csv","npy"], default="bin",
                    help="input format (default: bin)")
    ap.add_argument("--dtype", dest="dtype", default="uint8", help="input dtype (default: uint8)")
    ap.add_argument("--M", dest="M", type=int, default=256, help="alphabet size (default 256)")
    ap.add_argument("--fs", dest="fs", type=float, default=None, help="sampling rate (optional)")
    ap.add_argument("--out", dest="out", default="-", help="output PIF file or '-' for stdout")
    ap.add_argument("--pif-fmt", dest="pif_fmt", choices=["json","msgpack"], default="json",
                    help="PIF format (default: json)")
    ap.add_argument("--pretty", dest="pretty", action="store_true", help="pretty JSON (indent=2)")

    args = ap.parse_args()

    # load raw
    dtype = np.dtype(args.dtype)
    if args.inp == "-" or args.inp.strip() == "":
        x = _load_raw_from_stdin(args.in_fmt, dtype)
        inp_desc = "stdin"
    else:
        path = Path(args.inp)
        if not path.exists():
            ap.error(f"Input file not found: {path}")
        x = _load_raw_from_file(path, args.in_fmt, dtype)
        inp_desc = str(path)

    # build schema and encode
    codec = S1PhaseCodec(M=int(args.M))
    schema = {"alphabet": {"type": "uint", "M": int(args.M)}}
    if args.fs is not None:
        schema["sampling"] = {"fs": float(args.fs)}

    p = codec.encode(x, schema=schema)

    # serialize PIF
    if args.pif_fmt == "json":
        out_bytes = _serialize_pif_json(p, pretty=bool(args.pretty))
    else:
        out_bytes = _serialize_pif_msgpack(p)

    # write out
    if args.out == "-" or args.out.strip() == "":
        sys.stdout.buffer.write(out_bytes)
        sys.stdout.buffer.flush()
    else:
        Path(args.out).write_bytes(out_bytes)

    print(f"[pb-encode] {inp_desc} -> {args.out}  (N={x.size}, M={args.M}, fmt={args.pif_fmt})", file=sys.stderr)

if __name__ == "__main__":
    main()

