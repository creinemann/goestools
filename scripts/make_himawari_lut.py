#!/usr/bin/env python3
"""Make a Himawari-9 version of a GOES false-color LUT with natural land colors.

Why: the USRadioguy LUTs color the hottest land (left columns, warmest IR)
deep red/orange. GOES-19 rarely sees land that hot, but Himawari-9 looks
at the Australian outback, whose surface reaches 330 K+ at midday, so the
whole continent turned deep orange-red around local noon.

This keeps the LUT's ocean, cloud and night colors exactly as they are,
and repaints only the land columns (warm IR, left of the ocean colors)
with a natural palette, hottest first:
  red ochre (Pilbara-type red dirt) -> desert tan -> khaki -> olive green
then blends back into the original ocean colors by column C_END.
Brightness still comes from the visible channel (via the LUT's own
brightness at column LUM_COL), so salt lakes stay pale and shadows dark.

Usage: make_himawari_lut.py IN_LUT.png OUT_LUT.png
  share/usradioguy/usradioguy_night_lut.png -> himawari9_night_lut.png
  share/usradioguy/usradioguy_lut.png       -> himawari9_lut.png

Tuned on Himawari-9 relay imagery received in Horicon, 25 Nov 2026, with
himawari9_vs_curve.png and himawari9_ir_curve.png as the remap curves.
Ocean pixels there fall in LUT columns 43-56, land at midday in 0-36.
"""
import sys
import numpy as np
from PIL import Image

# (column, (R, G, B) chroma) - only the ratios matter; luminance is set below
STOPS = [
    (0,  (1.00, 0.70, 0.48)),   # hottest: red ochre
    (16, (1.00, 0.79, 0.58)),   # desert tan
    (28, (0.90, 0.85, 0.60)),   # khaki / dry grass
    (36, (0.66, 0.78, 0.46)),   # olive green (vegetation)
]
C_END = 43        # back to the original LUT (ocean) by this column
LUM_COL = 34      # take each row's brightness from the original LUT here
BRIGHT = 1.12     # land a little brighter than the original land colors

W = np.array([0.299, 0.587, 0.114])


def himawari_lut(lut):
    lut = lut.astype(float)
    out = lut.copy()
    lum = (lut[:, LUM_COL, :] @ W) * BRIGHT
    cols = np.array([c for c, _ in STOPS])
    chroma = np.array([rgb for _, rgb in STOPS], float)
    chroma /= (chroma @ W)[:, None]          # unit luminance
    last = cols[-1]
    for c in range(C_END):
        ch = np.array([np.interp(min(c, last), cols, chroma[:, k]) for k in range(3)])
        land = np.clip(np.outer(lum, ch), 0, 255)
        t = 0.0 if c <= last else (c - last) / (C_END - last)
        out[:, c, :] = land * (1 - t) + lut[:, c, :] * t
    return np.clip(np.rint(out), 0, 255).astype(np.uint8)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    src = np.array(Image.open(sys.argv[1]).convert("RGB"))
    assert src.shape == (256, 256, 3), "expected a 256x256 LUT"
    Image.fromarray(himawari_lut(src), "RGB").save(sys.argv[2])
    print("wrote", sys.argv[2])
