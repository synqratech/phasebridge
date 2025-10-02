# cli/pb_decode.py
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

from phasebridge.pif import PIF
from phasebridge.codec_s1 import S1PhaseCodec

def _detect_pif_fmt(path: Optional[Path], explicit: Optional[str]) -> str:
    if explicit:
        return explicit
    if path is None:
        return "json"  # stdin default
    suf = path.suffix.lower()
    if suf in (".mp", ".msgpack", ".mpk"):
        return "msgpack"
    return "json"

def _load_pif_json_bytes(b: bytes) -> PIF:
    s = b.decode("utf-8")
    return PIF.from_json(s, validate=True)

def _load_pif_msgpack_bytes(b: bytes) -> PIF:
    if not _HAVE_MSGPACK:
        raise RuntimeError("msgpack not installed. pip install msgpack")
    obj = msgpack.unpackb(b, raw=False)  # type: ignore
    if not isinstance(obj, dict):
        raise ValueError("msgpack root must be an object")
    return PIF.from_dict(obj, validate=True)

def _save_raw(x: np.ndarray, out_fmt: str, out_path: Optional[Path]) -> None:
    out_fmt = out_fmt.lower()
    if out_path is None:
        # stdout
        if out_fmt == "bin":
            sys.stdout.buffer.write(np.ascontiguousarray(x).tobytes())
            sys.stdout.buffer.flush()
        elif out_fmt == "csv":
            # print as integers separated by commas
            txt = ",".join(str(int(v)) for v in x.ravel())
            sys.stdout.write(txt)
            sys.stdout.flush()
        elif out_fmt == "npy":
            # write .npy stream to stdout
            np.save(sys.stdout.buffer, x)
            sys.stdout.buffer.flush()
        else:
            raise ValueError(f"Unsupported --out-fmt: {out_fmt}")
    else:
        # file
        if out_fmt == "bin":
            x.tofile(out_path)
        elif out_fmt == "csv":
            np.savetxt(out_path, x, fmt="%d", delimiter=",")
        elif out_fmt == "npy":
            np.save(out_path, x)
        else:
            raise ValueError(f"Unsupported --out-fmt: {out_fmt}")

def main():
    ap = argparse.ArgumentParser(
        description="PIF decoder (strict lossless): PIF (json/msgpack) -> raw (bin/csv/npy)"
    )
    ap.add_argument("--in", dest="inp", default="-", help="input PIF file or '-' for stdin")
    ap.add_argument("--pif-fmt", dest="pif_fmt", choices=["json","msgpack"], default=None,
                    help="PIF format (auto by ext; stdin default=json)")
    ap.add_argument("--out", dest="out", default="-", help="output raw file or '-' for stdout")
    ap.add_argument("--out-fmt", dest="out_fmt", choices=["bin","csv","npy"], default="bin",
                    help="output format (default: bin)")
    args = ap.parse_args()

    # read PIF bytes
    if args.inp == "-" or args.inp.strip() == "":
        b = sys.stdin.buffer.read()
        in_path = None
    else:
        in_path = Path(args.inp)
        if not in_path.exists():
            ap.error(f"Input file not found: {in_path}")
        b = in_path.read_bytes()

    pif_fmt = _detect_pif_fmt(in_path, args.pif_fmt)

    # parse PIF -> PIF object
    if pif_fmt == "json":
        p = _load_pif_json_bytes(b)
    else:
        p = _load_pif_msgpack_bytes(b)

    # instantiate codec with M from schema
    try:
        M = int(p.schema["alphabet"]["M"])
    except Exception:
        ap.error("PIF schema.alphabet.M missing or invalid")
        return

    codec = S1PhaseCodec(M=M)
    x = codec.decode(p)

    # write raw
    out_path = None if (args.out == "-" or args.out.strip() == "") else Path(args.out)
    _save_raw(x, args.out_fmt, out_path)

    in_desc = "stdin" if in_path is None else str(in_path)
    out_desc = "stdout" if out_path is None else str(out_path)
    print(f"[pb-decode] {in_desc} -> {out_desc}  (N={x.size}, M={M}, out_fmt={args.out_fmt})", file=sys.stderr)

if __name__ == "__main__":
    main()

