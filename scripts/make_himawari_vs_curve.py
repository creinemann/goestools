#!/usr/bin/env python3
"""Make a Himawari-9 VS (visible) contrast curve for goesproc.

The Himawari VS image relayed over GOES-West HRIT is roughly 2.5-3x
darker than GOES ABI ch02, so LUTs tuned for GOES (wxstar, USRadioguy)
look murky. This curve applies a linear GAIN, then the same wxstar ch02
curve GOES uses, so both satellites hit the LUT with similar brightness.

Usage: make_himawari_vs_curve.py WXSTAR_CH02_CURVE.png OUT.png [GAIN]
Use in goesproc as:  [handler.remap.vs]  path = "OUT.png"
"""
import sys
import numpy as np
from PIL import Image

base = np.array(Image.open(sys.argv[1]).convert("L")).ravel()
assert base.size == 256
gain = float(sys.argv[3]) if len(sys.argv) > 3 else 2.6
idx = np.clip(np.rint(np.arange(256) * gain), 0, 255).astype(int)
Image.fromarray(base[idx].astype(np.uint8).reshape(1, 256), "L").save(sys.argv[2])
print("wrote", sys.argv[2], "gain", gain)
