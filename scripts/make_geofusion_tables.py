#!/usr/bin/env python3
"""Make the Himawari-9 tables for USRG_GeoFusion and Himawari-9 IR Enhanced.

The Himawari relay carries no temperature calibration, so its colors are
borrowed from GOES: a GOES Channel 13 image and the matching ch13_enhanced
image (same scan, from the same station) give the exact enhancement color
for every Channel 13 grey level. himawari9_ir_curve.png already puts
Himawari IR on that GOES scale.

  make_geofusion_tables.py CH13NOMAP.jpg CH13_ENHANCED.jpg IR_CURVE.png OUT_DIR

Writes:
  himawari9_geofusion_table.png  color per GOES-scale IR level (for [handler.geofusion] table)
  himawari9_ir_enhanced.png      color per raw Himawari IR level (for [handler.remap.ir])
"""
import sys, os
import numpy as np, cv2

grey_path, enh_path, curve_path, out = sys.argv[1:5]
g = cv2.imread(grey_path, cv2.IMREAD_GRAYSCALE)
e = cv2.imread(enh_path, cv2.IMREAD_COLOR)
if g is None or e is None or g.shape != e.shape[:2]:
    sys.exit("need two images of the same scan and size")

# Only use smooth areas inside the disk (skips map lines and the limb)
h, w = g.shape
flat = np.abs(g.astype(int) - cv2.blur(g, (5, 5)).astype(int)) <= 2
yy, xx = np.mgrid[0:h, 0:w]
disk = ((yy - h / 2) ** 2 + (xx - w / 2) ** 2) < (0.48 * w) ** 2
G, E = g[flat & disk], e[flat & disk]

T = np.zeros((256, 3)); n = np.zeros(256, int)
for v in range(256):
    s = E[G == v]; n[v] = len(s)
    if len(s) >= 20:
        T[v] = np.median(s, 0)
good = n >= 20; idx = np.arange(256)
for c in range(3):
    T[~good, c] = np.interp(idx[~good], idx[good], T[good, c])

# Colder than any measured level: continue along the GOES ch13 gradient
P = [(333, '000000'), (273, 'b9b9b9'), (263, 'EAEAEA'), (253, '00ffff'), (238, '0000FF'), (237.999, '000080'),
     (235, '003300'), (230, '008000'), (222, 'ffff00'), (208, 'FF0000'), (198, 'FF7F7F'), (193.15, '800080'),
     (188, '301030'), (178, 'ffffff')]
P = [(k, np.array([int(c[i:i + 2], 16) for i in (0, 2, 4)], float)) for k, c in P]
def col(K):
    if K >= P[0][0]: return P[0][1]
    for (k0, c0), (k1, c1) in zip(P, P[1:]):
        if k1 <= K <= k0: return c0 + (c1 - c0) * (k0 - K) / (k0 - k1)
    return P[-1][1]
Ks = np.arange(170, 260, 0.05); C = np.array([col(k) for k in Ks])[:, ::-1]
cold = [v for v in range(idx[good].max() - 26, idx[good].max() + 1) if good[v]]
kk = [Ks[((C - T[v]) ** 2).sum(1).argmin()] for v in cold]
a, b = np.polyfit(cold, kk, 1)
for v in range(idx[good].max() + 1, 256):
    T[v] = col(a * v + b)[::-1]
T[:idx[good].min()] = T[idx[good].min()]

curve = cv2.imread(curve_path, cv2.IMREAD_UNCHANGED).reshape(-1)
os.makedirs(out, exist_ok=True)
table = (T + 0.5).astype(np.uint8)
cv2.imwrite(os.path.join(out, "himawari9_geofusion_table.png"), table.reshape(1, 256, 3))
raw = table[curve].copy(); raw[255] = 0      # 255 = outside the disk in the relay images
cv2.imwrite(os.path.join(out, "himawari9_ir_enhanced.png"), raw.reshape(1, 256, 3))
print("measured", good.sum(), "levels; wrote tables to", out)
