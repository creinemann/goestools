#!/usr/bin/env python3
"""Make the USRG_GeoColor data files (USRadioguy addition).

For each satellite view this writes, into OUT_DIR:
  <sat>_land.png        land mask (0..255) with a soft 1-pixel coastline
  <sat>_tint_01.jpg ... <sat>_tint_12.jpg
                        NASA Blue Marble Next Generation, one per month,
                        reprojected into the satellite's full-disk view
and once:
  luminance.png         256x1: brightness for each visible level, from the
                        USRadioguy LUT, so land is as bright as the live
                        visible channel says

Inputs:
  BM_DIR   the 12 monthly Blue Marble Next Generation images (plain, not
           "topo"/"bathy"), as NASA names them: world.200401...jpg to
           world.200412...jpg (any size; 21600x10800 or 5400x2700).
           https://visibleearth.nasa.gov (search "Blue Marble Next Generation")
  The land mask comes from Natural Earth (share/ne, public domain).

Usage:
  scripts/make_geocolor_data.py BM_DIR share/usradioguy/geocolor

Satellite views (full disk, as goesproc writes them):
  goes19     GOES-19 East, 75.2 W, ABI fixed grid
  goes18     GOES-18 West, 137.0 W, ABI fixed grid
  himawari9  Himawari-9, 140.7 E, as relayed over GOES-West HRIT (2200 px;
             the disk is measured from relayed images: centre and radius below)

Blue Marble imagery: NASA Earth Observatory / Reto Stockli (public domain).
"""
import glob
import json
import os
import re
import sys

import cv2
import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
HERE = os.path.dirname(os.path.abspath(__file__))
REQ, RPOL, HS = 6378137.0, 6356752.31414, 42164160.0
W3 = np.array([0.299, 0.587, 0.114])

VIEWS = {
    #            lon0     mask px  tint px  disk centre/radius (None = ABI fixed grid)
    'goes19':    (-75.2,  2712,    1356,    None),
    'goes18':    (-137.0, 2712,    1356,    None),
    'himawari9': (140.7,  2200,    1100,    (1099.0, 1099.2, 1085.4)),
}


def latlon(n, lon0, disk):
    """lat/lon of each pixel of an n x n full-disk image (NaN off the Earth)."""
    if disk is None:
        a = 0.303744 / n
        cx = cy = n / 2.0
    else:
        cx, cy, rad = (v * n / 2200.0 for v in disk)
        a = np.arcsin(REQ / HS) / rad
    jj, ii = np.mgrid[:n, :n].astype(np.float64)
    x = (ii + 0.5 - cx) * a
    y = (cy - jj - 0.5) * a
    A = np.sin(x)**2 + np.cos(x)**2 * (np.cos(y)**2 + (REQ**2 / RPOL**2) * np.sin(y)**2)
    B = -2 * HS * np.cos(x) * np.cos(y)
    C = HS**2 - REQ**2
    disc = B**2 - 4 * A * C
    ok = disc >= 0
    rs = (-B - np.sqrt(np.where(ok, disc, 0))) / (2 * A)
    sx = rs * np.cos(x) * np.cos(y)
    sy = -rs * np.sin(x)
    sz = rs * np.cos(x) * np.sin(y)
    lat = np.degrees(np.arctan((REQ**2 / RPOL**2) * sz / np.sqrt((HS - sx)**2 + sy**2)))
    lon = np.degrees(np.radians(lon0) - np.arctan(sy / (HS - sx)))
    lon = (lon + 180) % 360 - 180
    lat[~ok] = np.nan
    lon[~ok] = np.nan
    return lat, lon


def sample(eq, lat, lon, interp):
    h, w = eq.shape[:2]
    mx = ((lon + 180) / 360 * w).astype(np.float32)
    my = ((90 - lat) / 180 * h).astype(np.float32)
    mx[np.isnan(mx)] = -1
    my[np.isnan(my)] = -1
    return cv2.remap(eq, mx, my, interpolation=interp, borderMode=cv2.BORDER_WRAP if False else cv2.BORDER_CONSTANT, borderValue=0)


def land_raster(width=16000):
    """Natural Earth countries (lakes cut out) as an equirectangular 0/255 raster."""
    h = width // 2
    with open(os.path.join(HERE, '..', 'share', 'ne', 'ne_50m_admin_0_countries_lakes.json')) as f:
        feats = json.load(f)['features']
    polys = []
    for ft in feats:
        g = ft['geometry']
        for poly in (g['coordinates'] if g['type'] == 'MultiPolygon' else [g['coordinates']]):
            for k, ring in enumerate(poly):
                r = np.array(ring)
                pts = np.stack([(r[:, 0] + 180) / 360 * width, (90 - r[:, 1]) / 180 * h], 1)
                polys.append((k, np.round(pts * 8).astype(np.int32)))
    img = np.zeros((h, width), np.uint8)
    cv2.fillPoly(img, [p for k, p in polys if k == 0], 255, lineType=cv2.LINE_AA, shift=3)
    cv2.fillPoly(img, [p for k, p in polys if k > 0], 0, lineType=cv2.LINE_AA, shift=3)   # holes
    return img


def main(bm_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    months = {}
    for f in sorted(glob.glob(os.path.join(bm_dir, '*'))):
        m = re.search(r'2004(0[1-9]|1[0-2])', os.path.basename(f))
        if m and f.lower().endswith(('.jpg', '.jpeg', '.png')) and 'topo' not in f and 'bathy' not in f:
            months[int(m.group(1))] = f
    missing = [m for m in range(1, 13) if m not in months]
    if missing:
        sys.exit('missing Blue Marble months: %s' % missing)

    # brightness per visible level, from the USRadioguy LUT
    lut = np.array(Image.open(os.path.join(HERE, '..', 'share', 'usradioguy', 'usradioguy_lut.png')).convert('RGB')).astype(float)
    lum = np.maximum(lut[:, 38, :] @ W3, lut[:, 48, :] @ W3)
    Image.fromarray(np.clip(np.rint(lum), 0, 255).astype(np.uint8).reshape(256, 1), 'L').save(os.path.join(out_dir, 'luminance.png'))

    land_eq = land_raster()
    grids = {}
    for sat, (lon0, mpx, tpx, disk) in VIEWS.items():
        lat, lon = latlon(mpx, lon0, disk)
        mask = sample(land_eq, lat, lon, cv2.INTER_LINEAR)
        mask = cv2.GaussianBlur(mask, (0, 0), 1.2)
        Image.fromarray(mask, 'L').save(os.path.join(out_dir, sat + '_land.png'), optimize=True)
        grids[sat] = latlon(tpx, lon0, disk)
        print(sat, 'land mask', mask.shape, 'land %.1f%%' % (100 * (mask > 127).mean()))

    for m in range(1, 13):
        eq = np.array(Image.open(months[m]).convert('RGB').resize((5400, 2700), Image.LANCZOS))
        for sat in VIEWS:
            lat, lon = grids[sat]
            tint = sample(eq, lat, lon, cv2.INTER_LINEAR)
            Image.fromarray(tint, 'RGB').save(os.path.join(out_dir, '%s_tint_%02d.jpg' % (sat, m)), quality=88, optimize=True)
        print('month %02d done' % m)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
