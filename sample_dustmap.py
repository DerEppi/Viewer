"""
sample_dustmap.py
─────────────────
Sampelt die Edenhofer-(2024)-3D-Staubkarte auf ein reguläres kartesisches
Gitter um die Sonne und speichert das Ergebnis für den Viewer-Export.

  python sample_dustmap.py

Erzeugt: saves/values/dustmap_edenhofer.npz
  - density : float32-Array, Form (nx, ny, nz), lokale Extinktionsdichte
              (E von Zhang/Green/Rix 2023 pro pc), NaN außerhalb des
              Kartenbereichs (Edenhofer reicht 69–1250 pc).
  - origin  : [x0, y0, z0]   (pc, heliozentrisch galaktisch-kartesisch)
  - shape   : [nx, ny, nz]
  - spacing : [dx, dy, dz]   (pc)

WICHTIG: Dies nutzt integrated=False → LOKALE Dichte pro Voxel (für die
Dichtewolken-Darstellung). Das unterscheidet sich von einer evtl. schon
vorhandenen av_grid_flat.npy mit integrated=True (kumulative Säule bis zum
Punkt — dafür NICHT geeignet).

Läuft im selben Environment wie das NIFTy-Projekt (dustmaps + astropy).
Bei Bedarf vorher einmalig:  from dustmaps.edenhofer2023 import fetch; fetch()
"""

import os
import numpy as np
import astropy.units as u
from astropy.coordinates import Galactic, SkyCoord
from dustmaps.edenhofer2023 import Edenhofer2023Query

# ── Gitter-Konfiguration ───────────────────────────────────────────────────────
# Würfel zentriert auf die Sonne (0,0,0). Halbkantenlänge so gewählt, dass
# Taurus UND Orion (~ x=-343, y=-187, z=-124 pc) abgedeckt sind, aber innerhalb
# der Edenhofer-Reichweite (max. 1250 pc Radius) bleiben.
HALF_EXTENT = 450.0   # pc  → Box geht von -450 bis +450 in jeder Achse
VOXEL       = 5.0     # pc  → ~180 Voxel je Achse

OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saves", "values", "dustmap_edenhofer.npz")

# Edenhofer-Karte deckt nur 69–1250 pc Distanz ab; Punkte außerhalb → NaN.
DIST_MIN = 69.0
DIST_MAX = 1250.0

# Chunk-Größe für die Query (Speicher schonen; ein 180³-Gitter sind ~5.8 Mio
# Punkte, das in einem Rutsch durch astropy/dustmaps zu jagen kann viel RAM
# kosten — daher in Blöcken).
CHUNK = 200_000


def build_grid():
    n = int(round(2 * HALF_EXTENT / VOXEL))
    axis = np.linspace(-HALF_EXTENT, -HALF_EXTENT + n * VOXEL, num=n, endpoint=False)
    X, Y, Z = np.meshgrid(axis, axis, axis, indexing="ij")
    origin  = [float(axis[0])] * 3
    shape   = [n, n, n]
    spacing = [VOXEL] * 3
    return X, Y, Z, axis, origin, shape, spacing


def main():
    X, Y, Z, axis, origin, shape, spacing = build_grid()
    nx, ny, nz = shape
    print(f"Dust-Gitter: {nx} × {ny} × {nz} = {nx*ny*nz} Voxel "
          f"(±{HALF_EXTENT} pc, {VOXEL} pc Voxel)")

    x_flat = X.ravel()
    y_flat = Y.ravel()
    z_flat = Z.ravel()
    dist   = np.sqrt(x_flat**2 + y_flat**2 + z_flat**2)

    # Nur Punkte innerhalb der Kartenreichweite abfragen; Rest bleibt NaN.
    in_range = (dist >= DIST_MIN) & (dist <= DIST_MAX)
    n_query  = int(in_range.sum())
    print(f"Punkte innerhalb 69–1250 pc: {n_query} / {len(dist)} "
          f"({100*n_query/len(dist):.1f} %)")

    density_flat = np.full(len(dist), np.nan, dtype=np.float32)

    # dustmaps-Query initialisieren (integrated=False → lokale Dichte!)
    print("Lade Edenhofer-Karte (kann etwas dauern)…")
    dm = Edenhofer2023Query(integrated=False)

    idx_in = np.where(in_range)[0]
    xi = x_flat[idx_in]; yi = y_flat[idx_in]; zi = z_flat[idx_in]
    di = dist[idx_in]

    print(f"Sampling in {int(np.ceil(n_query / CHUNK))} Blöcken à {CHUNK}…")
    for start in range(0, n_query, CHUNK):
        end = min(start + CHUNK, n_query)
        # Gitter ist in galaktisch-kartesischen pc (u,v,w) gegeben → in (l,b,d)
        # bzw. SkyCoord mit Distanz wandeln, exakt wie im bestehenden
        # av_grid_flat-Code des Users.
        gal = Galactic(
            u=xi[start:end] * u.pc,
            v=yi[start:end] * u.pc,
            w=zi[start:end] * u.pc,
            representation_type="cartesian",
        )
        sc = SkyCoord(gal).icrs
        q  = SkyCoord(ra=sc.ra, dec=sc.dec, distance=di[start:end] * u.pc)
        vals = np.asarray(dm(q)).astype(np.float32)
        density_flat[idx_in[start:end]] = vals
        print(f"  {end}/{n_query}", end="\r", flush=True)
    print()

    density = density_flat.reshape(nx, ny, nz)

    finite = np.isfinite(density)
    if finite.any():
        vmax = float(np.nanpercentile(density[finite], 99))
        vmin = float(np.nanmin(density[finite]))
        print(f"Dichte-Wertebereich: [{vmin:.4g}, {np.nanmax(density[finite]):.4g}] "
              f"(99. Perzentil {vmax:.4g})")

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    np.savez_compressed(
        OUT_PATH,
        density=density,
        origin=np.array(origin, dtype=np.float64),
        shape=np.array(shape, dtype=np.int32),
        spacing=np.array(spacing, dtype=np.float64),
    )
    size_mb = os.path.getsize(OUT_PATH) / 1e6
    print(f"Gespeichert: {OUT_PATH}  ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()