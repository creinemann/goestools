#!/usr/bin/env python3
"""Add a night side to an existing goesproc false color LUT.

Most daytime LUTs (wxstar, USRadioguy custom) go black when the visible
channel is ~0, so the night half of the disk is empty even though the
IR channel still sees every cloud. This script keeps the base LUT
untouched wherever it is already brighter, and only fills the dark,
low-visible rows with an IR-driven blue-grey cloud layer that fades out
across the terminator.

LUT axes (as used by goesproc): row = visible (ch02 / Himawari VS),
column = IR (ch13 / Himawari IR), higher = colder.

Usage: make_night_lut.py BASE.png OUT.png
"""
import sys
import numpy as np
from PIL import Image

# --- knobs -----------------------------------------------------------
NIGHT_CLOUD = (150, 168, 196)   # colour of the coldest night cloud tops
NIGHT_SKY   = (4, 8, 20)        # night-side background (clear sky)
CLOUD_FROM, CLOUD_TO = 0.30, 0.85   # IR coldness range clouds fade in over
SPACE_TO = 0.10                     # IR counts below this fade to black (space)
FADE_FROM, FADE_TO = 0.02, 0.16     # visible range over which night fades out
# ---------------------------------------------------------------------

def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)

base_path, out_path = sys.argv[1], sys.argv[2]
base = np.array(Image.open(base_path).convert("RGB")).astype(np.float64)
assert base.shape == (256, 256, 3), "LUT must be 256x256"

y, x = np.mgrid[0:256, 0:256].astype(np.float64)
v, t = y / 255.0, x / 255.0

cloud_w = smooth(CLOUD_FROM, CLOUD_TO, t)[..., None]
night = np.array(NIGHT_SKY) + (np.array(NIGHT_CLOUD) - np.array(NIGHT_SKY)) * cloud_w
night_w = (1.0 - smooth(FADE_FROM, FADE_TO, v))[..., None]
# Off-disk space reads ~0 in both channels: keep it black.
night_w = night_w * smooth(0.0, SPACE_TO, t)[..., None]

# Never darken the base LUT: take the brighter of base and night layer.
out = np.maximum(base, night * night_w)
Image.fromarray(np.clip(np.rint(out), 0, 255).astype(np.uint8), "RGB").save(out_path)
print("wrote", out_path)
