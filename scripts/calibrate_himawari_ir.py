#!/usr/bin/env python3
"""Calibrate Himawari-9 IR (HRIT relay) onto the GOES ABI ch13 scale.

The relayed Himawari IR image uses a different count-to-temperature
scale than GOES CMIP ch13: warm surfaces sit around 14-26 instead of
~45-50, so GOES-tuned false color LUTs paint land red/orange instead of
green. This builds a remap curve by quantile-matching the full-disk IR
distributions of several GOES ch13 frames and Himawari IR frames.

Usage:
  calibrate_himawari_ir.py OUT.png --goes ch13_a.jpg ch13_b.jpg ... \\
                                   --himawari ir_a.jpg ir_b.jpg ...
Use 3+ frames of each, spread over the day. Image files are goesproc
output (grey JPG/PNG); white map lines and off-disk fill are ignored.
Use in goesproc as:  [handler.remap.ir]  path = "OUT.png"
"""
import argparse
import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

def disk_values(path, off):
    a = np.array(Image.open(path).convert("L"))
    step = max(1, a.shape[0] // 1800)
    a = a[::step, ::step]
    n = a.shape[0]
    yy, xx = np.mgrid[0:n, 0:n]
    inside = np.hypot(xx - n / 2, yy - n / 2) / (n / 2) < 0.95
    v = a[inside]
    return v[(v != off) & (v > 0) & (v < 250)]

ap = argparse.ArgumentParser()
ap.add_argument("out")
ap.add_argument("--goes", nargs="+", required=True)
ap.add_argument("--himawari", nargs="+", required=True)
args = ap.parse_args()

g = np.concatenate([disk_values(p, 0) for p in args.goes])
h = np.concatenate([disk_values(p, 255) for p in args.himawari])
q = np.linspace(0.2, 99.8, 400)
gq, hq = np.percentile(g, q), np.percentile(h, q)

x = np.arange(256)
f = np.interp(x, hq, gq)
lo, hi = int(hq[0]), hq[-1]
slope_lo = (gq[5] - gq[0]) / max(hq[5] - hq[0], 1)
f[:lo] = np.maximum(gq[0] - (lo - x[:lo]) * slope_lo, 0)
top = x > hi
f[top] = gq[-1] + (x[top] - hi) * (255 - gq[-1]) / max(255 - hi, 1)
f = np.maximum.accumulate(np.clip(f, 0, 255))
f = np.convolve(np.pad(f, 3, mode="edge"), np.ones(7) / 7, "valid")
curve = np.rint(f).astype(np.uint8)
curve[0] = 0   # off-disk pixels are blanked to 0 before remap; keep them black
Image.fromarray(curve.reshape(1, 256), "L").save(args.out)
print("wrote", args.out)
print("himawari -> goes:", [(int(i), int(curve[i])) for i in (10, 20, 35, 50, 100, 165, 220)])
