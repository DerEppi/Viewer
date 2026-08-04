"""
generate_local_bubble.py
─────────────────────────
Erzeugt mehrere feste Detailstufen der Local-Bubble-Punktwolke für den Viewer,
aus den rohen Pelgrims et al. (2020) HEALPix-Daten (L19_map-inner_final.fits).

  python generate_local_bubble.py

Erzeugt: saves/values/local_bubble_shell_points.npz
  Enthält ein Array pro Stufe, benannt "lod_<NSIDE>" (z.B. "lod_16", "lod_32"),
  jeweils shape (N,3), x/y/z in pc — JEDE Stufe ist eine eigenständige, echte
  HEALPix-Auflösung (gleichmäßig über die Himmelskugel verteilte Pixelmittel),
  keine Stichprobe einer feineren Stufe.

Die FITS-Datei enthält eine HEALPix-Tabelle bei NSIDE=128 (volle Auflösung,
196608 Pixel) mit mehreren vorgefertigten Spalten für unterschiedliche
sphärisch-harmonische Glättungsgrade (lmax):

  LMAX_COL    — welche Glättungsstufe der Oberfläche selbst verwendet wird.
                Höher = mehr Welligkeit/Struktur, aber auch mehr Rauschen aus
                der Kartenrekonstruktion (Pelgrims et al. empfehlen lmax=6 als
                Kompromiss zwischen Form und Überanpassung an Kartenrauschen).
  LOD_NSIDES  — Liste der zu erzeugenden Detailstufen (HEALPix NSIDE-Werte).
                NSIDE → Punktzahl: 8→768, 16→3072, 32→12288, 64→49152,
                128→196608 (= volle Rohauflösung, kein Downsampling).
                Der Viewer bekommt einen Slider, der zwischen genau diesen
                Stufen springt — wähle also so viele/wenige, wie im Viewer
                als Stufen sinnvoll sind (3-5 ist ein guter Bereich).
"""

import os
import numpy as np
import healpy as hp
from astropy.io import fits

_HERE = os.path.dirname(os.path.abspath(__file__))
FITS_PATH = os.path.join(_HERE, "L19_map_inner_final.fits")
OUT_PATH  = os.path.join(_HERE, "saves", "values", "local_bubble_shell_points.npz")

# Verfügbare Spalten in der Datei: r_inner_raw, r_in_lmax-02/04/06/08/10/20/30/40
LMAX_COL  = "r_in_lmax-06"   # bisheriger Standard (Pelgrims' empfohlener Kompromiss)

# Detailstufen, die der Viewer-Slider anbieten soll. Jede ist eine eigene,
# vollständige HEALPix-Auflösung (kein Subsampling einer anderen Stufe).
LOD_NSIDES = [8, 16, 32, 64, 128]


def _downsample(r, nside_in, nest_in, nside_out):
    """Mittelwert-Downsampling auf eine gröbere HEALPix-Auflösung."""
    if nside_out >= nside_in:
        return r, nside_in, nest_in
    r_ds = hp.ud_grade(r, nside_out, order_in="NESTED" if nest_in else "RING",
                        order_out="RING")
    return r_ds, nside_out, False


def _to_xyz(r_pix, nside, nest):
    npix = hp.nside2npix(nside)
    theta, phi = hp.pix2ang(nside, np.arange(npix), nest=nest)
    # HEALPix (theta, phi) -> Galactic Cartesian (gleiche Konvention wie die
    # übrigen Referenzobjekte: l = phi in Grad, b = 90° - theta in Grad).
    l_rad, b_rad = phi, np.pi/2 - theta
    x = r_pix * np.cos(b_rad) * np.cos(l_rad)
    y = r_pix * np.cos(b_rad) * np.sin(l_rad)
    z = r_pix * np.sin(b_rad)
    return np.column_stack([x, y, z])


def main():
    with fits.open(FITS_PATH) as hdul:
        data = hdul[1].data
        nside_in = hdul[1].header["NSIDE"]
        ordering = hdul[1].header["ORDERING"]
        if LMAX_COL not in data.columns.names:
            raise ValueError(f"Spalte {LMAX_COL!r} nicht in Datei. "
                              f"Verfügbar: {data.columns.names}")
        r = np.asarray(data[LMAX_COL], dtype=float)
    nest_in = (ordering.upper() == "NESTED")

    print(f"Eingelesen: NSIDE={nside_in} ({ordering}), {len(r)} Pixel, "
          f"Spalte {LMAX_COL!r}, r-Bereich [{r.min():.1f}, {r.max():.1f}] pc")

    arrays = {}
    for nside_out in sorted(set(LOD_NSIDES)):
        r_ds, nside_eff, nest_eff = _downsample(r, nside_in, nest_in, nside_out)
        pts = _to_xyz(r_ds, nside_eff, nest_eff)
        key = f"lod_{nside_out}"
        arrays[key] = pts.astype(np.float32)
        print(f"  {key}: NSIDE={nside_eff} → {len(pts)} Punkte"
              + ("" if nside_eff == nside_out else " (= volle Rohauflösung, "
                 f"{nside_out} war ≥ Quellauflösung {nside_in})"))

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    np.savez_compressed(OUT_PATH, **arrays)
    size_kb = os.path.getsize(OUT_PATH) / 1e3
    print(f"Gespeichert: {OUT_PATH}  ({len(arrays)} Stufen, {size_kb:.1f} KB)")


if __name__ == "__main__":
    main()