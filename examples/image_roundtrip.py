# examples/image_roundtrip.py
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image  # pip install pillow

from phasebridge.codec_s1 import S1PhaseCodec
from phasebridge.pif import PIF
from phasebridge.kappa import kappa_timeseries
from phasebridge.utils import sha256_of_array


def load_image_as_uint8_L(path: Path) -> tuple[np.ndarray, dict]:
    """
    Load an image and convert it to 8-bit grayscale ('L').
    Returns (arr(H,W) uint8, meta_dict with original mode/size).
    """
    img = Image.open(path)
    src_mode = img.mode
    src_size = img.size  # (W, H)
    if img.mode != "L":
        img = img.convert("L")  # строго 8-bit grayscale
    arr = np.asarray(img, dtype=np.uint8)
    return arr, {"src_mode": src_mode, "src_size": src_size, "mode": "L"}

def save_uint8_L_as_image(path: Path, arr_hw: np.ndarray) -> None:
    """
    Save a 2D uint8 array as PNG (grayscale 'L').
    """
    if arr_hw.dtype != np.uint8 or arr_hw.ndim != 2:
        raise ValueError("Expected 2D uint8 array")
    out_img = Image.fromarray(arr_hw, mode="L")
    out_img.save(path, format="PNG")

def main():
    ap = argparse.ArgumentParser(
        description="Image round-trip demo: 8-bit grayscale image -> PIF(JSON) -> image, strict equality"
    )
    ap.add_argument("--in-img", required=True, help="input image (any mode; will be converted to 8-bit L)")
    ap.add_argument("--out-pif", required=True, help="path to save PIF JSON")
    ap.add_argument("--out-img", required=True, help="path to save reconstructed PNG image (8-bit L)")
    ap.add_argument("--M", type=int, default=256, help="alphabet size (for 8-bit L use 256)")
    args = ap.parse_args()

    in_img = Path(args.in_img)
    out_pif = Path(args.out_pif)
    out_img = Path(args.out_img)
    M = int(args.M)

    if not in_img.exists():
        print(f"Input image not found: {in_img}", file=sys.stderr)
        sys.exit(1)

    # 1) Load and convert to 8-bit L
    arr_hw, imeta = load_image_as_uint8_L(in_img)  # HxW, uint8
    H, W = arr_hw.shape
    x = arr_hw.reshape(-1)  # flatten

    # 2) Encode into PIF
    codec = S1PhaseCodec(M=M)
    schema = {
        "alphabet": {"type": "uint", "M": M},
        "image": {"height": H, "width": W, "mode": "L", "src_mode": imeta["src_mode"], "src_size": imeta["src_size"]},
    }
    p = codec.encode(x, schema=schema)

    # 3) Save PIF as JSON
    out_pif.write_text(p.to_json(indent=2), encoding="utf-8")

    # 4) Decode back
    p2 = PIF.from_json(out_pif.read_text(encoding="utf-8"), validate=True)
    x_rec = codec.decode(p2)
    arr_rec = x_rec.reshape(H, W)

    # 5) Save reconstructed image
    save_uint8_L_as_image(out_img, arr_rec)

    # 6) Strict checks: array equality and hash validation
    arrays_equal = bool(np.array_equal(arr_hw, arr_rec))
    sha_in = sha256_of_array(arr_hw)
    sha_rec = sha256_of_array(arr_rec)
    sha_meta = p.meta.get("hash_raw", None)
    hash_ok = (sha_meta is None) or (sha_in == sha_meta == sha_rec)

    # 7) κ-metric (computed on flattened phase array)
    kappa_val = kappa_timeseries(p, weighted=False, validate=False)

    # 8) Report
    report = {
        "ok": arrays_equal and hash_ok,
        "M": M,
        "H": H,
        "W": W,
        "arrays_equal": arrays_equal,
        "sha256_in": sha_in,
        "sha256_rec": sha_rec,
        "sha256_meta": sha_meta,
        "hash_ok": hash_ok,
        "kappa": float(kappa_val),
        "in_img": str(in_img),
        "out_pif": str(out_pif),
        "out_img": str(out_img),
        "note": p.meta.get("note", None),
        "src_mode": imeta["src_mode"],
        "src_size": imeta["src_size"],
        "mode": "L"
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))

    sys.exit(0 if report["ok"] else 2)

if __name__ == "__main__":
    main()
