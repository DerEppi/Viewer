"""
export_vectorfield.py  (Viewer/ — gemeinsamer Export für BEIDE Repos)
─────────────────────
Berechnet alle Feldgrößen direkt aus den NIFTy-Ergebnissen und bettet sie in
die HTML-Vorlage (Viewer/vectorfield_viewer.html) ein.

    REPO unten wählen ("taurus" | "claude") — oder per CLI überschreiben:
      ../TaurusVelocityField/.venv/bin/python export_vectorfield.py taurus
      ../ClaudeVelocityField/.venv/bin/python export_vectorfield.py claude [result_name]

    taurus → TaurusVelocityField (Thesis-Runs, alte Pipeline):
             Runs/<name>/results/last.pkl + Parameters/<name>.py,
             simple_functions.py im Repo-Root, eta-Rekonstruktion aus den
             Posterior-Latents.  Venv: TaurusVelocityField/.venv
    claude → ClaudeVelocityField (neue vfield-Pipeline):
             Runs/<name>/last.pkl + parameters_used.txt (kann nie vom
             Checkpoint abdriften), Visualisation/simple_functions.py,
             rv_used aus dem ECHTEN Inferenz-Datenlader (vfield). eta wird
             (noch) nicht rekonstruiert — andere Latent-Struktur; die Felder
             bleiben leer und der Viewer blendet sie aus.
             Venv: ClaudeVelocityField/.venv

Erzeugt: Viewer/vectorfield_viewer_data.html. meta.repo ("T"/"C") +
result_name zeigt der Viewer als "[T] final_run" (HUD + Help → Loaded Result).

Für mehrere Felder: FIELDS-Liste erweitern (selbe Logik, anderer result_name
/ star_csv / masses_csv). Reference-Objekte (Sonne, Shells, Regionen, Dustmap)
bleiben global außerhalb der Feld-Schleife.
"""

# ── Repo-Wahl ─────────────────────────────────────────────────────────────────
REPO = "taurus"          # "taurus" | "claude"  (CLI-Argument 1 überschreibt)

import json
import math
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import erf
from scipy.interpolate import RegularGridInterpolator
from astropy.coordinates import Galactic, ICRS
import astropy.units as u_ap

if len(sys.argv) > 1:
    REPO = sys.argv[1]
REPO = str(REPO).strip().lower()   # case-insensitiv: "Taurus"/"CLAUDE"/… ok
if REPO not in ("taurus", "claude"):
    sys.exit(f"REPO muss 'taurus' oder 'claude' sein, nicht {REPO!r}")

VIEWER_DIR  = Path(__file__).resolve().parent
WORKSPACE   = VIEWER_DIR.parent
TAURUS_ROOT = WORKSPACE / "TaurusVelocityField"
CLAUDE_ROOT = WORKSPACE / "ClaudeVelocityField"
REPO_ROOT   = TAURUS_ROOT if REPO == "taurus" else CLAUDE_ROOT
REPO_TAG    = "T" if REPO == "taurus" else "C"
print(f"Repo: {REPO} [{REPO_TAG}] — {REPO_ROOT}")

# Beide Modi arbeiten mit Repo-relativen Pfaden (Runs/, Data/, Parameters.*)
os.chdir(REPO_ROOT)
if REPO == "taurus":
    sys.path.insert(0, str(REPO_ROOT))
    from simple_functions import (
        apply_models, calculate_mask, load_models, load_parameters, load_samples,
        gal_to_icrs,
    )
else:
    # Visualisation/simple_functions setzt selbst den vfield-sys.path (ROOT)
    sys.path.insert(0, str(REPO_ROOT / "Visualisation"))
    from simple_functions import (
        apply_models, calculate_mask, load_models, load_parameters, load_samples,
        gal_to_icrs,
    )
    from vfield.data_loading import load_stellar_data

# ── Ausgabe-Konfiguration ──────────────────────────────────────────────────────
HTML_TEMPLATE          = VIEWER_DIR / "vectorfield_viewer.html"
HTML_OUTPUT            = VIEWER_DIR / "vectorfield_viewer_data.html"
SAVE_JSON              = True
JSON_OUTPUT            = VIEWER_DIR / "saves/vectorfield_data.json"
SAVE_HTML_LIGHT        = True
HTML_OUTPUT_LIGHT      = VIEWER_DIR / "vectorfield_viewer_light.html"
# Light-Version: ohne Dustmap und nur mit den N gröbsten Local-Bubble-Stufen
LIGHT_LB_LEVELS        = 2

# ── Feld-Konfiguration je Repo (CLI-Argument 2 überschreibt result_name) ───────
# Alle Felder teilen dieselbe Logik; reference_objects sind global.
FIELDS_BY_REPO = {
    "taurus": [
        dict(
            result_name = "final_run",
            star_csv    = "Data/taurus_core_sigma_age-Feb-2025-luhman-comparison.csv",
            masses_csv  = "Data/Chronos.csv",
            label       = "Taurus",
        ),
    ],
    "claude": [
        dict(
            result_name = "test_run",
            star_csv    = "Data/taurus_core_sigma_age-Feb-2025-luhman-comparison.csv",
            masses_csv  = "../Chronos/Masses/results.csv",
            label       = "Taurus",
            # KDE-Massendichte-Schwelle für die Viewer-Maske (die neuen Configs
            # haben keine posterior_plotting-Sektion mehr; Wert wie plot_data.py)
            mask_level  = 0.0005,
        ),
    ],
}
FIELDS = FIELDS_BY_REPO[REPO]
if len(sys.argv) > 2:
    FIELDS[0]["result_name"] = sys.argv[2]

# Referenz-Assets (Local-Bubble-/Dustmap-npz): eigener Ordner zuerst, dann die
# saves/values beider Repos (dort liegen die bereits berechneten Dateien).
_ASSET_DIRS = [
    VIEWER_DIR / "saves" / "values",
    TAURUS_ROOT / "saves" / "values",
    CLAUDE_ROOT / "saves" / "values",
]

def _find_asset(name):
    for d in _ASSET_DIRS:
        if (d / name).exists():
            return d / name
    return None

# Sonnenbewegung relativ zum LSR (Schönrich et al. 2010, U,V,W in km/s)
SUN_MOTION_LSR = [11.1, 12.2, 7.3]

# Bandbreiten-Faktor der KDE-Massendichte (scipy gaussian_kde bw_method-Skalar:
# Kovarianz = Datenkovarianz · smooth²). Wandert als meta.kde in den Export, damit
# der Viewer die Dichte LIVE neu rechnen kann (andere Bandbreite / nur bestimmte
# Sterngruppen) und mit diesem Wert exakt die exportierte Dichte reproduziert.
KDE_SMOOTH = 0.2


# =============================================================================
# Hilfsfunktionen
# =============================================================================

def _minmax(arr, mask):
    """Min/Max über endliche Maskenvoxel."""
    vals = arr[mask]
    vals = vals[np.isfinite(vals)]
    return (float(vals.min()), float(vals.max())) if len(vals) else (0.0, 1.0)

def _f(v):
    try:
        f = float(v)
        return None if np.isnan(f) else round(f, 4)
    except Exception:
        return None

def _sid(v):
    s = str(v).strip() if v is not None else ""
    return s if s and s.lower() != "nan" else None

def _cat(v):
    """Kategorie-String (Gruppenname) → None für 'kein Wert'.

    Das Stern-CSV kodiert 'gehört zu keiner Luhman-Gruppe' als '-'; im Viewer
    ist das ein fehlender Wert (grauer Punkt, ∅-Toggle), kein eigener Name.
    """
    s = str(v).strip() if v is not None else ""
    return s if s and s not in ("-", "nan", "NaN", "None") else None

def _icrs_to_gal_uvw(ra_deg, dec_deg, dist_pc, pmra, pmdec, rv):
    """ICRS (ra,dec,dist,pmra,pmdec,rv) -> Galactic Cartesian velocity U,V,W [km/s].
    Self-contained (statt aus simple_functions importiert — das Claude-Repo hat
    kein icrs_to_gal), identische astropy-Transformation wie
    TaurusVelocityField/simple_functions.py:icrs_to_gal. Mit rv=0 liefert das
    die reine PM-Geschwindigkeit (tangential, ohne Radialanteil) — s.
    plot_data.py U_star_pm_only."""
    coords = ICRS(
        ra=ra_deg * u_ap.deg, dec=dec_deg * u_ap.deg, distance=dist_pc * u_ap.pc,
        pm_ra_cosdec=pmra * (u_ap.mas/u_ap.yr), pm_dec=pmdec * (u_ap.mas/u_ap.yr),
        radial_velocity=rv * (u_ap.km/u_ap.s),
    )
    gal = coords.transform_to(Galactic())
    gal.representation_type = "cartesian"
    gal.differential_type = "cartesian"
    return (gal.U.to(u_ap.km/u_ap.s).value,
            gal.V.to(u_ap.km/u_ap.s).value,
            gal.W.to(u_ap.km/u_ap.s).value)

def _num(x):
    """Voxel value → float, aber NaN/Inf → None. Sonst schriebe json.dumps ein
    NaN-Literal (ungültiges JSON für die SAVE_JSON-Datei; im HTML-Embed liest
    der Viewer die Felder mit `?? 0`, null wird also sauber zu 0)."""
    x = float(x)
    return x if math.isfinite(x) else None

def _gal_lbd_to_xyz(l, b, d_pc):
    lr, br = np.radians(l), np.radians(b)
    return [float(d_pc*np.cos(br)*np.cos(lr)),
            float(d_pc*np.cos(br)*np.sin(lr)),
            float(d_pc*np.sin(br))]

def _region_kinematics(l, b, d_pc, pm_l_cosb, pm_b, vr):
    c = Galactic(l=l*u_ap.deg, b=b*u_ap.deg, distance=d_pc*u_ap.pc,
                 pm_l_cosb=pm_l_cosb*u_ap.mas/u_ap.yr,
                 pm_b=pm_b*u_ap.mas/u_ap.yr,
                 radial_velocity=vr*u_ap.km/u_ap.s)
    cart = c.cartesian; vel = cart.differentials['s']
    pos = [float(cart.x.to(u_ap.pc).value),
           float(cart.y.to(u_ap.pc).value),
           float(cart.z.to(u_ap.pc).value)]
    uvw = [float(vel.d_x.to(u_ap.km/u_ap.s).value),
           float(vel.d_y.to(u_ap.km/u_ap.s).value),
           float(vel.d_z.to(u_ap.km/u_ap.s).value)]
    return [round(p,2) for p in pos], [round(v,2) for v in uvw]


# =============================================================================
# Noise-Estimation eta (InvGamma-Faktor pro rv-Stern)
# =============================================================================
# Die rv-Likelihood skaliert jede rv-Varianz mit eta ~ InvGamma(alpha, q):
# sigma_eff = rv_err·√eta. eta existiert nur für Sterne, die MIT rv in die
# Inferenz gingen, in deren Reihenfolge; mit n_parallax_samples zerfallen sie
# in zwei Latent-Vektoren ("_w_rv" gute / "_w_rv_sampled" gesampelte Parallaxe).
# Ground truth ist das Posterior (Key-Längen) — die Parameterfiles sind teils
# gedriftet. Die Sternmenge wird deshalb aus Gaia.csv (der Datenquelle der
# Inferenz, NICHT dem Stern-CSV) rekonstruiert und gegen die Längen verifiziert.

def _eta_parallax_bad(parameters, gaia):
    """distance_cut_filter der Inferenz: Parallaxe legt den Stern mit
    Wahrscheinlichkeit < par_min_prob_mass in sein eigenes Voxel."""
    geo = parameters["geometry"]
    shape, dists = geo["shape"], geo["distances"]
    par     = gaia["parallax"].values.astype(float)
    par_err = gaia["parallax_error"].values.astype(float)
    c = ICRS(ra=gaia["ra"].values*u_ap.deg, dec=gaia["dec"].values*u_ap.deg,
             distance=(1000.0/par)*u_ap.pc).transform_to(Galactic())
    x = np.abs(np.array(c.cartesian.x.value))
    y = np.abs(np.array(c.cartesian.y.value))
    z = np.abs(np.array(c.cartesian.z.value))
    r = np.sqrt(x**2 + y**2 + z**2)
    l2i = [((s - 1) / s) / d for s, d in zip(shape, dists)]
    t_min = np.maximum.reduce([np.floor(a*l)/l/a for a, l in zip((x, y, z), l2i)])
    t_max = np.minimum.reduce([np.ceil(a*l)/l/a  for a, l in zip((x, y, z), l2i)])
    p_min = 1.0/(t_max*r)*1000.0
    p_max = 1.0/(t_min*r)*1000.0
    par_integral = 0.5*(erf((p_max - par)/(np.sqrt(2)*par_err)) -
                        erf((p_min - par)/(np.sqrt(2)*par_err)))
    return par_integral < parameters["data"]["data_set_kwargs"]["par_min_prob_mass"]


def _eta_from_posterior(parameters, samples, gaia, n_stars):
    """→ (eta_mean, eta_std, has_rv_mask), alles CSV-zeilengleich; NaN/None wenn
    der Run keine Noise-Estimation hat oder die Sternmenge nicht verifizierbar ist."""
    nan = np.full(n_stars, np.nan)
    tree = samples.samples.tree
    base_keys    = [k for k in tree if k.startswith("noise_estimate_") and k.endswith("_w_rv")]
    sampled_keys = [k for k in tree if k.startswith("noise_estimate_") and k.endswith("_w_rv_sampled")]
    if len(base_keys) != 1 or not parameters["model"].get("do_noise_estimation"):
        if base_keys:
            print(f"eta: {len(base_keys)} Populationen — nicht unterstützt, übersprungen.")
        return nan, nan, None

    nek   = parameters["model"]["noise_estimation_kwargs"]
    alpha = nek["alpha"]
    q     = nek["q"]
    if isinstance(q, str):
        q = alpha - 1 if q == "mean_is_one" else alpha + 1

    dsk    = parameters["data"]["data_set_kwargs"]
    rv_g   = gaia["radial_velocity"].values.astype(float)
    rve_g  = gaia["radial_velocity_error"].values.astype(float)
    ruwe_g = gaia["ruwe"].values.astype(float)

    def has_rv_mask(ruwe_thr, buggy_integral, err_max):
        rv, rve = rv_g.copy(), rve_g.copy()
        if dsk.get("filter_ruwe") and ruwe_thr is not None:
            bad = ruwe_g > ruwe_thr
            rv[bad] = np.nan; rve[bad] = np.nan
        f = np.isfinite(rv) & np.isfinite(rve)
        hi = dsk["rv_max"] - (rve[f] if buggy_integral else rv[f])
        integ = 0.5*(erf(hi/(np.sqrt(2)*rve[f])) -
                     erf((dsk["rv_min"] - rv[f])/(np.sqrt(2)*rve[f])))
        g = np.zeros(n_stars, bool); g[f] = integ > dsk["rv_min_prob_mass"]; f = g
        if err_max is not None:
            g = np.zeros(n_stars, bool); g[f] = rve[f] < err_max; f = g
        return f

    # Kandidaten-Strategien für die rv-Sternmenge, in Prioritätsreihenfolge:
    # 1) heutiger stellar_data.py-Stand mit den Parameterfile-Werten,
    # 2) Legacy-Stand der final_run-Ära (ruwe 1.4 hart verdrahtet, fehlerhafte
    #    rv_integral-Formel mit rv_err statt rv, noch kein filter_rv_error).
    cands = []
    if not dsk.get("filter_ruwe") or dsk.get("ruwe_threshold") is not None:
        cands.append(("aktuell", has_rv_mask(dsk.get("ruwe_threshold"), False, dsk.get("filter_rv_error"))))
    cands.append(("legacy-2026", has_rv_mask(1.4, True, None)))

    key_b = base_keys[0]
    key_s = sampled_keys[0] if sampled_keys else None
    n_b = int(np.shape(tree[key_b])[-1])
    n_s = int(np.shape(tree[key_s])[-1]) if key_s else 0
    if key_s and dsk.get("par_min_prob_mass") is None:
        print("eta: '_w_rv_sampled' ohne par_min_prob_mass — nicht rekonstruierbar.")
        return nan, nan, None
    bad_par = _eta_parallax_bad(parameters, gaia) if key_s else np.zeros(n_stars, bool)

    for strat, m in cands:
        m_b = m & ~bad_par
        m_s = m & bad_par
        if m_b.sum() == n_b and m_s.sum() == n_s:
            break
    else:
        got = [f"{s}: {int((m & ~bad_par).sum())}+{int((m & bad_par).sum())}" for s, m in cands]
        print(f"eta: keine Strategie trifft Posterior ({n_b}+{n_s}); Kandidaten: {got} — übersprungen.")
        return nan, nan, None

    import jax
    import nifty8.re as jft
    eta_mean = np.full(n_stars, np.nan)
    eta_std  = np.full(n_stars, np.nan)
    for key, sel in ((key_b, m_b), (key_s, m_s)):
        if key is None or not sel.any():
            continue
        es = np.asarray(jax.vmap(
            jft.InvGammaPrior(alpha, q, name=key, shape=(int(sel.sum()),))
        )(samples.samples))
        rows = np.flatnonzero(sel)
        eta_mean[rows] = es.mean(axis=0)
        eta_std[rows]  = es.std(axis=0)
    print(f"eta: Strategie '{strat}', {n_b}+{n_s} rv-Sterne, "
          f"Median {np.nanmedian(eta_mean):.2f}, Max {np.nanmax(eta_mean):.1f}")
    return eta_mean, eta_std, m


# =============================================================================
# Pro-Feld-Verarbeitung
# =============================================================================

def process_field(cfg):
    """
    Lädt NIFTy-Ergebnisse und Sterndaten, berechnet alle abgeleiteten Größen,
    gibt das fertige Feld-Dict zurück (voxels, real_stars, meta).
    """
    result_name = cfg["result_name"]
    print(f"\n── Feld: {cfg['label']} ({result_name}) ──")

    # ── NIFTy-Samples laden ──────────────────────────────────────────────────
    if REPO == "taurus":
        parameters = load_parameters(f"Parameters.{result_name}")
        samples    = load_samples(f"Runs/{result_name}/results")
    else:
        # neue Pipeline: parameters_used.txt im Run-Ordner ist die Wahrheit
        parameters = load_parameters(f"Runs/{result_name}")
        samples    = load_samples(f"Runs/{result_name}")
    model      = load_models(parameters)
    v_mean, v_std = apply_models(model, samples)

    geo = parameters["geometry"]
    BOX_ORIGIN    = geo["origin"]
    BOX_SHAPE     = geo["shape"]
    BOX_DISTANCES = geo["distances"]

    xyz = [
        np.linspace(BOX_ORIGIN[i],
                    BOX_ORIGIN[i] + BOX_SHAPE[i] * BOX_DISTANCES[i],
                    num=BOX_SHAPE[i], endpoint=False)
        for i in range(3)
    ]
    nx, ny, nz = BOX_SHAPE

    vx, vy, vz         = v_mean
    vx_std, vy_std, vz_std = v_std
    print(f"Grid: {nx}×{ny}×{nz} = {nx*ny*nz} Voxel")

    # ── Sterndaten ───────────────────────────────────────────────────────────
    Taurus_core     = pd.read_csv(cfg["star_csv"], dtype={"source_id": str})
    _star_ids       = Taurus_core["source_id"].astype(np.int64).values
    # Chronos-Massen per source_id alignen (Zeilenreihenfolge nicht garantiert)
    Chronos         = (pd.read_csv(Path(cfg["masses_csv"]).resolve())
                       .set_index("source_id").reindex(_star_ids))
    mass            = Chronos["mass_solar"].values
    # Massen-Fehlerbereich (mass_hi − mass_lo, positiv) als zusätzliches
    # 2D-Plot-Färbe-/Achsenfeld im Viewer.
    mass_lo         = Chronos["mass_lo"].values
    mass_hi         = Chronos["mass_hi"].values
    # Photometrie (aus Chronos, zeilengleich zum Star-CSV): Gaia-Farben + abs. G,
    # als zusätzliche Färbe-/Plot-Felder im Viewer.
    bp_rp           = Chronos["BP-RP"].values
    g_rp            = Chronos["G-RP"].values
    abs_g_mag       = Chronos["abs_g_mag"].values

    star_x   = Taurus_core["X"].values
    star_y   = Taurus_core["Y"].values
    star_z   = Taurus_core["Z"].values
    star_age = Taurus_core["age_myr"].values
    pmra     = Taurus_core["pmra"].values
    pmdec    = Taurus_core["pmdec"].values
    rv       = Taurus_core["radial_velocity"].values
    pmra_err = Taurus_core["pmra_error"].values
    pmdec_err= Taurus_core["pmdec_error"].values
    rv_err   = Taurus_core["radial_velocity_error"].values
    ruwe     = Taurus_core["ruwe"].values
    av       = Taurus_core["av"].values
    # Gruppennamen (kategorisch, '-' = keiner Gruppe zugeordnet): Luhman-Census und
    # SigMA-Clustering. Optional — ältere Stern-CSVs haben die Spalten nicht, dann
    # blendet der Viewer die jeweilige Farb-/Filteroption aus.
    name_luhman = (Taurus_core["name_luhman"].values
                   if "name_luhman" in Taurus_core.columns else None)
    name_sigma  = (Taurus_core["name_sigma"].values
                   if "name_sigma" in Taurus_core.columns else None)
    star_U   = Taurus_core["U"].values.astype(float)
    star_V   = Taurus_core["V"].values.astype(float)
    star_W   = Taurus_core["W"].values.astype(float)
    source_id= Taurus_core["source_id"].values

    # Reine PM-Geschwindigkeit (rv=0) — für ALLE Sterne verfügbar, auch ohne
    # RV-Messung (anders als U/V/W oben). Viewer-Option "PM only" bei den
    # UVW-Pfeilen, analog plot_data.py U_star_pm_only.
    star_ra   = Taurus_core["ra"].values
    star_dec  = Taurus_core["dec"].values
    star_dist = 1000.0 / Taurus_core["parallax"].values.astype(float)   # pc
    U_pm, V_pm, W_pm = _icrs_to_gal_uvw(star_ra, star_dec, star_dist, pmra, pmdec, np.zeros_like(pmra))

    if REPO == "taurus":
        # RUWE-Schwelle für den rv_used-Fallback (final_run-Ära hat den Key nicht
        # im Parameterfile — dort war 1.4 in stellar_data.py hart verdrahtet)
        RUWE_THRESHOLD = parameters["data"]["data_set_kwargs"].get("ruwe_threshold", 1.4)
        # RV-Outlier-Filter (Integral-Wahrscheinlichkeit innerhalb [rv_min, rv_max])
        rv_min       = parameters["data"]["data_set_kwargs"]["rv_min"]
        rv_max       = parameters["data"]["data_set_kwargs"]["rv_max"]
        rv_min_prob  = parameters["data"]["data_set_kwargs"]["rv_min_prob_mass"]
        rv_nan_ok    = ~np.isnan(rv) & ~np.isnan(rv_err)
        rv_integral  = 0.5 * (
            erf((rv_max - rv[rv_nan_ok]) / (np.sqrt(2) * rv_err[rv_nan_ok])) -
            erf((rv_min - rv[rv_nan_ok]) / (np.sqrt(2) * rv_err[rv_nan_ok]))
        )
        rv_in_range          = np.full(rv_nan_ok.shape, False)
        rv_in_range[rv_nan_ok] = rv_integral > rv_min_prob
        rv_corrected         = rv.astype(float).copy()
        rv_corrected[~rv_in_range] = np.nan
        # rv_used = Filterkategorien (heutiger stellar_data.py-Stand): korrektes
        # rv-Integral + filter_ruwe + filter_rv_error. Bewusst NICHT die eta-/
        # Posterior-Menge — final_run-Ära-Runs liefen mit der fehlerhaften
        # rv_integral-Formel; deren tatsächliche Sternmenge weicht ab (s. u.).
        _dsk = parameters["data"]["data_set_kwargs"]
        rv_good_mask = ~np.isnan(rv_corrected)
        if _dsk.get("filter_ruwe", True):
            rv_good_mask &= ruwe < RUWE_THRESHOLD
        if _dsk.get("filter_rv_error") is not None:
            rv_good_mask &= rv_err < _dsk["filter_rv_error"]
    else:
        # rv_used = die ECHTE Inferenz-Maske: derselbe Datenlader wie im Run
        # (RUWE-Threshold, RV-Fenster/prob-mass, rv-error-Cut aus parameters_used) —
        # eine Filter-Nachbildung könnte vom tatsächlich Verwendeten abweichen.
        _data_cfg = dict(parameters["data"])
        _data_cfg["path"] = str(REPO_ROOT / "Data") + "/"
        sd = load_stellar_data(_data_cfg, parameters["geometry"])
        rv_good_mask = (
            pd.Series(sd.rv_valid, index=sd.source_id)
            .reindex(_star_ids)          # Sterne außerhalb der Auswahl → False
            .fillna(False)
            .to_numpy(dtype=bool)
        )

    # ── Noise-Estimation eta ─────────────────────────────────────────────────
    if REPO == "taurus":
        # Gaia.csv ist die Datenquelle der Inferenz (das Stern-CSV enthält
        # zusätzliche nicht-Gaia-rvs); Zeilen per source_id angleichen.
        _gaia = pd.read_csv(os.path.join(os.path.dirname(cfg["star_csv"]) or ".", "Gaia.csv"),
                            dtype={"source_id": str})
        # source_id bleibt Index (nur zum Zeilen-Alignment gebraucht; die eta-
        # Funktionen lesen nur Datenspalten). Kein reset_index → kein Spalten-
        # Insert in den sehr breiten Gaia-Frame (löst sonst pandas' Fragmentation-
        # PerformanceWarning aus).
        _gaia = _gaia.set_index("source_id").loc[source_id]
        eta_mean, eta_std, _eta_has_rv = _eta_from_posterior(
            parameters, samples, _gaia, len(star_x))
        # eta bleibt an die TATSÄCHLICHE Inferenz-Sternmenge gebunden (NaN außerhalb,
        # zeilengleich zum Stern-CSV) und überschreibt rv_used NICHT — bei Runs mit
        # dem rv_integral-Bug (final_run-Ära) weichen die Mengen ab.
        if _eta_has_rv is not None and not np.array_equal(_eta_has_rv, rv_good_mask):
            _n_f = int((rv_good_mask & ~_eta_has_rv).sum())
            _n_e = int((_eta_has_rv & ~rv_good_mask).sum())
            print(f"Hinweis: Inferenz-rv-Menge (eta) != Filterkategorien: "
                  f"{_n_f} nur Filter / {_n_e} nur Inferenz — rv_used folgt den "
                  f"Filterkategorien, eta bleibt None außerhalb der Inferenz-Menge.")
    else:
        # Neue Pipeline: andere Latent-Struktur (noise_estimate_exact/sampled) —
        # Rekonstruktion hier (noch) nicht implementiert. Alle eta-Felder bleiben
        # None, der Viewer blendet sie aus.
        print("eta: Rekonstruktion für die neue Pipeline nicht implementiert — Felder bleiben leer.")
        eta_mean = np.full(len(star_x), np.nan)
        eta_std  = np.full(len(star_x), np.nan)
    with np.errstate(invalid="ignore"):
        log10_eta = np.log10(eta_mean)

    # ── KDE-Dichte & Maske ────────────────────────────────────────────────────
    _kde_kw = dict(box_origin=BOX_ORIGIN, box_shape=BOX_SHAPE,
                   box_distances=BOX_DISTANCES,
                   star_x=star_x, star_y=star_y, star_z=star_z, smooth=KDE_SMOOTH)
    density      = calculate_mask(**_kde_kw, masses=None)
    mass_density = calculate_mask(**_kde_kw, masses=mass)
    mask_level   = cfg.get("mask_level")
    if mask_level is None:  # alte Configs tragen den Wert in posterior_plotting
        mask_level = parameters["posterior_plotting"]["density_mask_level"]
    mask_bool    = mass_density > mask_level
    mask_bool_flat = mask_bool.ravel()

    # ── Referenzrahmen & Bulk-Velocity ────────────────────────────────────────
    norm  = np.sum(mass_density)
    v_ref = np.array([np.sum(mass_density * vx) / norm,
                      np.sum(mass_density * vy) / norm,
                      np.sum(mass_density * vz) / norm])

    # ── Curl & Divergenz ──────────────────────────────────────────────────────
    dx, dy, dz = BOX_DISTANCES
    dvx_dx, dvx_dy, dvx_dz = np.gradient(vx, dx, dy, dz)
    dvy_dx, dvy_dy, dvy_dz = np.gradient(vy, dx, dy, dz)
    dvz_dx, dvz_dy, dvz_dz = np.gradient(vz, dx, dy, dz)
    divergence = dvx_dx + dvy_dy + dvz_dz
    curl_x = dvz_dy - dvy_dz
    curl_y = dvx_dz - dvz_dx
    curl_z = dvy_dx - dvx_dy
    curl_mag = np.sqrt(curl_x**2 + curl_y**2 + curl_z**2)
    std_mag  = np.sqrt(vx_std**2 + vy_std**2 + vz_std**2)

    # ── Residuen ──────────────────────────────────────────────────────────────
    X, Y, Z = np.meshgrid(xyz[0], xyz[1], xyz[2], indexing="ij")
    x_flat = X.ravel(); y_flat = Y.ravel(); z_flat = Z.ravel()

    pmra_field, pmdec_field, rv_field = gal_to_icrs(
        x_flat, y_flat, z_flat, vx.ravel(), vy.ravel(), vz.ravel())
    _interp_kw = dict(method="linear", bounds_error=False, fill_value=np.nan)
    _star_pts  = np.column_stack([star_x, star_y, star_z])
    pmra_at_stars  = RegularGridInterpolator(xyz, pmra_field.reshape(BOX_SHAPE),  **_interp_kw)(_star_pts)
    pmdec_at_stars = RegularGridInterpolator(xyz, pmdec_field.reshape(BOX_SHAPE), **_interp_kw)(_star_pts)
    rv_at_stars    = RegularGridInterpolator(xyz, rv_field.reshape(BOX_SHAPE),    **_interp_kw)(_star_pts)
    pmra_residual  = np.abs(pmra  - pmra_at_stars)
    pmdec_residual = np.abs(pmdec - pmdec_at_stars)
    rv_residual    = np.abs(rv    - rv_at_stars)
    rv_residual[~rv_good_mask] = np.nan

    # Gewichtete Residuen.
    # taurus: Residuum / Katalogfehler (bewusst OHNE sigma_int — so wurden die
    #   alten Runs diagnostiziert); rv zusätzlich in Einheiten des eta-
    #   inflationierten Fehlers sigma·sqrt(eta).
    # claude: sigma_eff = sqrt(sigma_gaia² + sigma_int² [+ sigma_rv_jitter² auf
    #   rv]) wie in der Likelihood (PM via kappa·d nach mas/yr projiziert);
    #   INFERIERTE Werte (Prior-Dict in der Config) werden als Posterior-Mittel
    #   des jeweiligen Latents gelesen. sigma_rv_jitter ist rv-only.
    if REPO == "claude":
        KAPPA = 4.740470463533

        def _sigma_cfg(key):
            val = parameters["model"].get(key, 0.0)
            if isinstance(val, dict):
                import nifty.re as jft
                prior = jft.LogNormalPrior(val["mean"], val["std"], name=key, shape=())
                val = float(np.mean([np.asarray(prior(s)) for s in samples]))
                print(f"{key} inferiert -> Posterior-Mittel {val:.3f} km/s")
            return float(val)

        _si  = _sigma_cfg("sigma_int")
        _jit = _sigma_cfg("sigma_rv_jitter")
        _d_kpc     = 1.0 / Taurus_core["parallax"].values.astype(float)  # 1/mas = kpc
        _s_int_mas = _si / (KAPPA * _d_kpc)
        pmra_err_eff  = np.hypot(pmra_err,  _s_int_mas)
        pmdec_err_eff = np.hypot(pmdec_err, _s_int_mas)
        rv_err_eff    = np.hypot(np.hypot(rv_err, _si), _jit)
        print(f"weighted residuals: sigma_eff mit sigma_int = {_si:.3f} km/s, "
              f"sigma_rv_jitter = {_jit:.3f} km/s")
    else:
        pmra_err_eff, pmdec_err_eff, rv_err_eff = pmra_err, pmdec_err, rv_err
    pmra_residual_w  = pmra_residual  / pmra_err_eff
    pmdec_residual_w = pmdec_residual / pmdec_err_eff
    rv_residual_w    = rv_residual    / rv_err_eff
    rv_residual_eta  = rv_residual    / (rv_err_eff * np.sqrt(eta_mean))

    print(f"v_ref = {v_ref}")

    # ── Colorbar-Normierung ───────────────────────────────────────────────────
    curl_min, curl_max = _minmax(curl_mag, mask_bool)
    div_min,  div_max  = _minmax(divergence, mask_bool)
    std_min,  std_max  = _minmax(std_mag, mask_bool)
    density_min = float(np.nanmin(density))
    density_max = float(np.nanmax(density))

    # ── Voxel-Array aufbauen ─────────────────────────────────────────────────
    IX, IY, IZ = np.meshgrid(np.arange(nx), np.arange(ny), np.arange(nz), indexing="ij")
    columns = {
        "x": np.round(X.ravel(), 3), "y": np.round(Y.ravel(), 3), "z": np.round(Z.ravel(), 3),
        "ix": IX.ravel().astype(int), "iy": IY.ravel().astype(int), "iz": IZ.ravel().astype(int),
        "vx": np.round(vx.ravel(), 4), "vy": np.round(vy.ravel(), 4), "vz": np.round(vz.ravel(), 4),
        "curl_x": np.round(curl_x.ravel(), 5), "curl_y": np.round(curl_y.ravel(), 5),
        "curl_z": np.round(curl_z.ravel(), 5),
        "div":    np.round(divergence.ravel(), 5),
        "std_x":  np.round(vx_std.ravel(), 4), "std_y": np.round(vy_std.ravel(), 4),
        "std_z":  np.round(vz_std.ravel(), 4),
        "density": np.round(density.ravel(), 6),
        # KDE-MASSENdichte pro Voxel: der Viewer berechnet die Maske daraus
        # LIVE (mass_density > mask_level, einstellbar per Slider). Deshalb kein
        # gebackenes mask-Bool mehr, und curl/div/std bleiben ÜBERALL erhalten
        # (bei kleinerem Level braucht der Viewer sie auch außerhalb der
        # Default-Maske).
        "mass_density": np.round(mass_density.ravel(), 8),
    }
    keys = list(columns.keys())
    voxels = [{k: (int(v) if k in ("ix","iy","iz") else _num(v)) for k, v in zip(keys, row)}
              for row in zip(*[columns[k].tolist() for k in keys])]
    print(f"Maskenvoxel (Default-Level {mask_level}): {int(mask_bool_flat.sum())}")

    # ── Sternobjekte ─────────────────────────────────────────────────────────
    real_stars = []
    for i in range(len(star_x)):
        real_stars.append({
            "source_id": _sid(source_id[i]),
            "x": _f(star_x[i]), "y": _f(star_y[i]), "z": _f(star_z[i]),
            "age": _f(star_age[i]), "ruwe": _f(ruwe[i]),
            "pmra": _f(pmra[i]), "pmdec": _f(pmdec[i]), "rv": _f(rv[i]),
            "mass": _f(mass[i]), "extinction": _f(av[i]),
            # positiver Fehlerbereich der Masse (NaN → None via _f, wenn lo/hi fehlt)
            "mass_err": _f(mass_hi[i] - mass_lo[i]),
            "BP-RP": _f(bp_rp[i]), "G-RP": _f(g_rp[i]), "abs_g_mag": _f(abs_g_mag[i]),
            "pmra error": _f(pmra_err[i]), "pmdec error": _f(pmdec_err[i]),
            "rv error": _f(rv_err[i]),
            "pmra residual": _f(pmra_residual[i]),
            "pmdec residual": _f(pmdec_residual[i]),
            "rv residual": _f(rv_residual[i]),
            "pmra residual weighted": _f(pmra_residual_w[i]),
            "pmdec residual weighted": _f(pmdec_residual_w[i]),
            "rv residual weighted": _f(rv_residual_w[i]),
            "rv residual eta weighted": _f(rv_residual_eta[i]),
            "eta": _f(eta_mean[i]), "eta std": _f(eta_std[i]),
            "log10 eta": _f(log10_eta[i]),
            "U": _f(star_U[i]), "V": _f(star_V[i]), "W": _f(star_W[i]),
            "U_pm": _f(U_pm[i]), "V_pm": _f(V_pm[i]), "W_pm": _f(W_pm[i]),
            # rv_good (rv filtered by the inference mask) was dropped: it is just
            # "rv" for the stars where rv_used is true, so the viewer reproduces
            # it via the "RV used in inference" mask instead of a separate field.
            "rv_used": bool(rv_good_mask[i]),
            "name_luhman": _cat(name_luhman[i]) if name_luhman is not None else None,
            "name_sigma":  _cat(name_sigma[i])  if name_sigma  is not None else None,
        })
    n_used = sum(1 for s in real_stars if s["rv_used"])
    print(f"Sterne: {len(real_stars)},  Inference-verwendet: {n_used}")

    # ── voxel_volume für Energieintegral (live im Viewer berechnet) ───────────
    voxel_volume = float(np.prod(BOX_DISTANCES))

    return {
        "meta": {
            "label":      cfg["label"],
            "shape":      [nx, ny, nz],
            "spacing": [
                round(float(xyz[0][1]-xyz[0][0]), 3) if nx>1 else float(BOX_DISTANCES[0]),
                round(float(xyz[1][1]-xyz[1][0]), 3) if ny>1 else float(BOX_DISTANCES[1]),
                round(float(xyz[2][1]-xyz[2][0]), 3) if nz>1 else float(BOX_DISTANCES[2]),
            ],
            "extent": {
                "x": [round(float(xyz[0][0]),2), round(float(xyz[0][-1]),2)],
                "y": [round(float(xyz[1][0]),2), round(float(xyz[1][-1]),2)],
                "z": [round(float(xyz[2][0]),2), round(float(xyz[2][-1]),2)],
            },
            "v_ref":          [round(float(v),4) for v in v_ref],
            "sun_motion_lsr": [round(float(c),2) for c in SUN_MOTION_LSR],
            "voxel_volume":   round(voxel_volume, 4),
            # Default-Maskenschwelle (KDE-Massendichte): Startwert des Viewer-
            # Sliders UND fixe Maske für das Energie-Integral. Die *_min/max
            # darunter sind über die DEFAULT-Maske gerechnet (Fallback; der
            # Viewer rechnet Auto-Ranges live über die aktuelle Maske).
            "mask_level":     float(mask_level),
            # KDE-Rezept der Massendichte, damit der Viewer sie LIVE neu rechnen
            # kann (Bandbreite umstellen, nur ausgewählte Sterngruppen gewichten).
            # ⚠️ Das Auswertegitter von simple_functions.calculate_mask ist NICHT
            # das Voxelgitter: np.mgrid legt `shape` Punkte INKLUSIVE beider Enden
            # über [origin, origin+shape·distance], die Schrittweite ist dort also
            # shape/(shape-1)·distance statt distance (xyz oben ist endpoint=False).
            # origin/shape/distances gehen deshalb roh mit — der Viewer baut damit
            # exakt dasselbe Gitter und reproduziert die exportierte Dichte.
            "kde": {
                "smooth":    float(KDE_SMOOTH),
                "origin":    [float(v) for v in BOX_ORIGIN],
                "shape":     [int(v) for v in BOX_SHAPE],
                "distances": [float(v) for v in BOX_DISTANCES],
            },
            "curl_min": round(curl_min,5), "curl_max": round(curl_max,5),
            "div_min":  round(div_min,5),  "div_max":  round(div_max,5),
            "std_min":  round(std_min,4),  "std_max":  round(std_max,4),
            "density_min": round(density_min,6), "density_max": round(density_max,6),
            "result_name": result_name,
            # Quell-Repo des Runs: "T" = TaurusVelocityField, "C" =
            # ClaudeVelocityField — der Viewer zeigt "[T] <result_name>".
            "repo": REPO_TAG,
            "star_color_fields": [
                "age", "rv", "pmra", "pmdec", "mass", "mass_err", "extinction", "ruwe",
                "pmra error", "pmdec error", "rv error",
                "pmra residual", "pmdec residual", "rv residual",
                "pmra residual weighted", "pmdec residual weighted",
                "rv residual weighted", "rv residual eta weighted",
                "eta", "eta std", "log10 eta",
                "U", "V", "W", "BP-RP", "G-RP", "abs_g_mag",
            ],
        },
        "voxels":     voxels,
        "real_stars": real_stars,
    }


# =============================================================================
# Referenz-Objekte (global, feld-unabhängig)
# =============================================================================

_region_raw = {
    "Lupus":      (-21.80,   8.99, 0.16, -23.40, -10.55,  0.16),
    "Ophiuchus":  ( -7.12,  19.48, 0.14, -24.13, -10.12, -7.82),
    "Chamaeleon": (-56.42, -14.67, 0.20, -20.54,  -6.61, 10.06),
    "Perseus":    (158.45, -20.74, 0.29,  11.31,  -2.71, 10.30),
    "Orion":      (-151.64,-18.44, 0.39,   0.87,   0.49, 23.14),
    "lambda Ori": (-165.46,-11.39, 0.40,   2.30,   0.27, 25.48),
}
_region_color = {
    "Lupus":"#5be8a0","Ophiuchus":"#43c9b0","Chamaeleon":"#7ce06a",
    "Perseus":"#ffb454","Orion":"#ff6b9d","lambda Ori":"#ff9d54",
}
region_objects = []
for nm,(l,b,dkpc,pml,pmb,vr) in _region_raw.items():
    pos,uvw = _region_kinematics(l,b,dkpc*1000,pml,pmb,vr)
    region_objects.append({"name":nm,"type":"region","pos":pos,"uvw":uvw,"color":_region_color[nm]})

_taurus_pos,_taurus_uvw = _region_kinematics(171.67,-15.46,130,21.85,-9.69,14.91)
taurus_object = {"name":"Taurus","type":"region","pos":_taurus_pos,"uvw":_taurus_uvw,"color":"#7fd9ff"}

_position_only_raw = {
    "Musca":            (301.5, -9.0,  171.0, "#5be8a0"),
    "Corona Australis": (359.9, -17.8, 150.0, "#c98cff"),
    "Pipe":             (0.0,    3.4,  150.0, "#8cc9ff"),
}
position_only_objects = [
    {"name":nm,"type":"position_only","pos":[round(p,2) for p in _gal_lbd_to_xyz(l,b,dpc)],"color":col}
    for nm,(l,b,dpc,col) in _position_only_raw.items()
]

_shell_center = _gal_lbd_to_xyz(161.1,-22.7,218.0)
shell_object = {"name":"Per-Tau Shell","type":"shell",
                "center":[round(c,2) for c in _shell_center],"radius":78.0,"color":"#9d8cff"}

_oe_center = _gal_lbd_to_xyz(-160.0,-20.0,280.0)
orion_eridanus_object = {"name":"Orion-Eridanus Superbubble (approx.)","type":"ellipsoid_shell",
                         "center":[round(c,2) for c in _oe_center],
                         "semi_axes":[125.0,100.0,100.0],"tilt_deg":32.0,"color":"#ff8c5a"}

sun_object = {"name":"Sun","type":"sun","pos":[0.0,0.0,0.0],"color":"#ffd24a"}

# Local Bubble
_lb_path = _find_asset("local_bubble_shell_points.npz")
local_bubble_object = None
if _lb_path is not None:
    import base64
    _lb_npz = np.load(_lb_path)
    # Kompaktes 16-Bit-Format (analog zur Dustmap-q8): statt xyz-Float-Listen als
    # JSON (~1.4 MB) werden die Schalenpunkte je Stufe uint16-quantisiert über
    # eine gemeinsame Bounding-Box und als base64 abgelegt (~0.5 MB, ~2.7× kleiner).
    # Der Viewer (_decodeLbubbleLevel) dequantisiert zurück nach pc.
    _lb_arrs = {int(k.split("_")[1]): np.asarray(_lb_npz[k], dtype=np.float64)
                for k in _lb_npz.files}
    _all = np.concatenate([a for a in _lb_arrs.values()]) if _lb_arrs else np.zeros((0, 3))
    _mn = _all.min(axis=0); _mx = _all.max(axis=0)
    _span = np.where(_mx > _mn, _mx - _mn, 1.0)
    _levels_q16 = {}
    for k, a in sorted(_lb_arrs.items()):
        q = np.round((a - _mn) / _span * 65535.0).clip(0, 65535).astype("<u2")  # (n,3) interleaved xyz
        _levels_q16[str(k)] = base64.b64encode(q.tobytes()).decode("ascii")
    local_bubble_object = {"name": "Local Bubble", "type": "point_cloud", "color": "#6fd6ff",
                           "bbox": {"min": [round(float(v), 3) for v in _mn],
                                    "max": [round(float(v), 3) for v in _mx]},
                           "levels_q16": _levels_q16}
    print(f"Local Bubble: {len(_lb_arrs)} Stufen (NSIDE {sorted(_lb_arrs)}), 16-bit kompakt")
else:
    print("Hinweis: local_bubble_shell_points.npz in keinem Asset-Verzeichnis gefunden.")

# Dustmap — kompaktes 8-Bit-Format (Juli 2026): Der Staub liegt auf einem
# regulären Gitter, also werden KEINE xyz/val-Listen mehr exportiert (~60 MB
# JSON), sondern EIN dichtes Uint8-Array als base64 (~8 MB): 0 = unter Cutoff,
# 1..255 = log-quantisiert zwischen val_cut und val_max. Der Viewer
# (buildDustCloud) rekonstruiert Positionen aus grid.origin/spacing/shape und
# dequantisiert zurück nach val/val_max (Shader-Attribut "dens"). Werte über
# val_max (99.5. Perzentil) clampen auf 255 — wie vorher über val_max geclampt.
_dust_path = _find_asset("dustmap_edenhofer.npz")
dustmap_object = None
if _dust_path is not None:
    import base64
    _dz = np.load(_dust_path)
    _dens = _dz["density"].astype(np.float32)
    _d_origin = _dz["origin"].astype(float)
    _d_spacing = _dz["spacing"].astype(float)
    _finite = np.isfinite(_dens)
    if _finite.any():
        _vmax = float(np.nanpercentile(_dens[_finite], 99.5))
        _cut  = float(np.nanpercentile(_dens[_finite], 60.0))
        _sel = _finite & (_dens > _cut) & (_dens > 0)
        _q = np.zeros(_dens.shape, dtype=np.uint8)
        _t = (np.log(_dens[_sel]) - np.log(_cut)) / (np.log(_vmax) - np.log(_cut))
        _q[_sel] = 1 + np.round(np.clip(_t, 0.0, 1.0) * 254).astype(np.uint8)
        _b64 = base64.b64encode(_q.ravel(order="C").tobytes()).decode("ascii")
        dustmap_object = {"name":"Dust (Edenhofer 2024)","type":"dust_cloud",
                          "grid":{"origin":[float(v) for v in _d_origin],
                                  "spacing":[float(v) for v in _d_spacing],
                                  "shape":[int(v) for v in _dens.shape]},
                          "q8":_b64,
                          "val_cut":float(_cut),"val_max":round(_vmax,4),
                          "spacing":round(float(_d_spacing[0]),2),
                          "color":"#c8a86a"}
        print(f"Dustmap: {int(_sel.sum())} Voxel > Cutoff, "
              f"Gitter {_dens.shape} als q8/base64 ({len(_b64)/1e6:.1f} MB).")
else:
    print("Hinweis: dustmap_edenhofer.npz in keinem Asset-Verzeichnis gefunden.")

reference_objects = {
    "sun": sun_object, "taurus": taurus_object, "shell": shell_object,
    "orion_eridanus": orion_eridanus_object,
    "regions": region_objects, "extra_clouds": position_only_objects,
    "citations": [
        "Per-Tau Shell (Zentrum + Radius, deren Table 1): Bialy et al. 2021 (arXiv:2109.09763)",
        "Regionen & Taurus Kinematik: Zhou, Li & Chen 2025, arXiv:2509.18496",
        "Local Bubble: Pelgrims et al. 2020, A&A 636, A17 (doi:10.7910/DVN/RHPVNC)",
        "Orion-Eridanus (Näherung): Joubaud et al. 2020; Pon et al. 2014/2016; Bally 2008",
        "Musca/CrA/Pipe: Zucker et al. 2020/2021 (arXiv:2109.09765)",
    ],
}
if local_bubble_object: reference_objects["local_bubble"] = local_bubble_object
if dustmap_object:
    reference_objects["dustmap"] = dustmap_object
    reference_objects["citations"].append(
        "Dustmap: Edenhofer et al. 2024, A&A 685, A82 (arXiv:2308.01295)")


# =============================================================================
# Felder verarbeiten und JSON zusammenbauen
# =============================================================================

processed_fields = [process_field(cfg) for cfg in FIELDS]

# Aktuell: einzelnes Feld in DATA (Abwärtskompatibel zum Viewer).
# Für mehrere Felder: data["fields"] = processed_fields, Viewer-Anpassung nötig.
field = processed_fields[0]
data = {
    "meta":              field["meta"],
    "voxels":            field["voxels"],
    "real_stars":        field["real_stars"],
    "reference_objects": reference_objects,
}

json_str = json.dumps(data, separators=(',',':'))

if SAVE_JSON:
    with open(JSON_OUTPUT, "w", encoding="utf-8") as f: f.write(json_str)
    print(f"JSON: {JSON_OUTPUT}  ({os.path.getsize(JSON_OUTPUT)/1e6:.1f} MB)")

# =============================================================================
# HTML einbetten
# =============================================================================
with open(HTML_TEMPLATE, encoding="utf-8") as f: html = f.read()
PLACEHOLDER = "/* __EMBEDDED_DATA__ */"
DATA_BLOCK  = f"const EMBEDDED_DATA = {json_str};"
if PLACEHOLDER not in html:
    print(f"FEHLER: Platzhalter nicht in {HTML_TEMPLATE}!"); exit(1)
html = html.replace(PLACEHOLDER, DATA_BLOCK)
with open(HTML_OUTPUT, "w", encoding="utf-8") as f: f.write(html)
print(f"Gespeichert: {HTML_OUTPUT}  ({os.path.getsize(HTML_OUTPUT)/1e6:.1f} MB)")

if SAVE_HTML_LIGHT:
    ro_nd = {k:v for k,v in reference_objects.items() if k!="dustmap"}
    # Nach der Dustmap ist die Local Bubble der größte Brocken: die feinen
    # NSIDE-Stufen machen den Löwenanteil ihrer Punkte aus. Die Light-Version
    # behält nur die zwei GRÖBSTEN Stufen. Der Viewer leitet den Detail-Slider
    # aus den vorhandenen Stufen ab (refreshLocalBubbleSlider → lbubbleNsides)
    # und klemmt einen gespeicherten, jetzt zu großen Index fest — es braucht
    # also keine Sonderbehandlung auf der Viewer-Seite.
    _lb_nd = ro_nd.get("local_bubble")
    if _lb_nd and _lb_nd.get("levels_q16"):
        _keep = sorted(_lb_nd["levels_q16"], key=int)[:LIGHT_LB_LEVELS]
        ro_nd["local_bubble"] = dict(
            _lb_nd, levels_q16={k: _lb_nd["levels_q16"][k] for k in _keep})
        print(f"Light: Local Bubble nur NSIDE {_keep} "
              f"(von {sorted(_lb_nd['levels_q16'], key=int)})")
    d_nd  = dict(data, reference_objects=ro_nd)
    js_nd = json.dumps(d_nd, separators=(',',':'))
    html_nd = html.replace(DATA_BLOCK, f"const EMBEDDED_DATA = {js_nd};")
    with open(HTML_OUTPUT_LIGHT, "w", encoding="utf-8") as f: f.write(html_nd)
    print(f"Gespeichert (ohne Dustmap): {HTML_OUTPUT_LIGHT}  ({os.path.getsize(HTML_OUTPUT_LIGHT)/1e6:.1f} MB)")