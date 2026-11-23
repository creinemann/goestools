#!/usr/bin/env python3
"""Generate the USRadioguy false color LUT for goesproc.

goesproc false color maps two 8-bit channels through a 256x256 RGB
table: row (y) = first channel  (GOES ch02 / Himawari VS, visible),
           column (x) = second channel (GOES ch13 / Himawari IR, 10.3um;
           higher counts = colder).

Design goals:
  * dark navy oceans, green/tan land, sandy deserts
  * low/warm clouds a soft warm grey, high/cold clouds bright white
  * deep convection (very bright + very cold) a crisp ice-blue white
  * the night side is NOT black: cold IR cloud tops stay visible in
    blue-grey so the terminator blends smoothly

Usage: make_usradioguy_lut.py [output.png]
Every knob below is a plain number; tweak and re-run.
"""
import sys
import numpy as np
from PIL import Image

def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)

def lerp(a, b, w):
    return a + (b - a) * w[..., None]

def c(r, g, b):
    return np.array([r, g, b], dtype=np.float64)

y, x = np.mgrid[0:256, 0:256].astype(np.float64)
v = y / 255.0          # visible reflectance (after contrast curve)
t = x / 255.0          # IR coldness

# Surface. Land vs. water is decided mostly by IR warmth (sunlit land
# is warmer than ocean), then shaded by visible reflectance.
ocean_dark  = c(6, 20, 52)
ocean_light = c(24, 62, 104)          # shallow water / sun glint
veg         = c(52, 92, 42)
arid        = c(136, 116, 76)
desert      = c(204, 176, 124)
ocean = lerp(ocean_dark, ocean_light, smooth(0.05, 0.30, v))
land  = lerp(veg, arid, smooth(0.12, 0.30, v))
land  = lerp(land, desert, smooth(0.30, 0.48, v))
land_w = 1.0 - smooth(0.08, 0.26, t)
surface = lerp(ocean, land, land_w)

# Clouds: warm low cloud = soft warm grey, cold high cloud = white
low_cloud  = c(200, 196, 188)
high_cloud = c(246, 248, 252)
ice_top    = c(214, 236, 255)
cloud = lerp(low_cloud, high_cloud, smooth(0.35, 0.75, t))
cloud = lerp(cloud, ice_top, smooth(0.82, 0.97, t) * smooth(0.55, 0.85, v))
cloudiness = np.maximum(
    smooth(0.42, 0.85, v),                         # bright = cloud
    0.85 * smooth(0.45, 0.80, t) * smooth(0.10, 0.35, v),  # cold + some vis
)
day = lerp(surface, cloud * (0.75 + 0.25 * v)[..., None], cloudiness)

# Night side: visible ~0, use IR only
night_bg    = c(4, 8, 22)
night_cloud = c(150, 168, 196)
night = lerp(night_bg, night_cloud, smooth(0.30, 0.85, t))
night_w = 1.0 - smooth(0.015, 0.10, v)

rgb = lerp(day, night, night_w)
lut = np.clip(np.rint(rgb), 0, 255).astype(np.uint8)

out = sys.argv[1] if len(sys.argv) > 1 else "usradioguy_lut.png"
Image.fromarray(lut, "RGB").save(out)
print("wrote", out, lut.shape)
