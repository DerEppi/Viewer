# Taurus Vectorfield Viewer — Claude Code Briefing (Stand: Oktober 2026)

Doc für den 3D-Viewer in **`Viewer/`** (Workspace-Root, repo-übergreifend); liegt im
Viewer-Repo selbst als `CLAUDE.md` (Workspace-Index: `../.claude/CLAUDE.md`). Nur Dauerhaftes: Regeln, Architektur-Wegweiser (wo was im Code
steht), bekannte Bugs+Lösungen. Erledigte Feature-Historie wird NICHT protokolliert.

## Was ist das?
Interaktiver, self-contained 3D-Viewer (eine HTML-Datei, kein Server) für ein Geschwindigkeits-
vektorfeld im Taurus-Molekülwolken-Komplex, rekonstruiert aus Gaia-Sternbewegungen via
NIFTy-Bayesianischer Inferenz. Teil einer Bachelorarbeit.

## Dateien
**Code liegt in `Viewer/` neben den beiden Repos.** Die alten Kopien in den Repos wurden
GELÖSCHT — nur die gebackenen `vectorfield_viewer_data*.html` im Taurus-Repo liegen noch
(stehende Regel: nicht löschen).
- `Viewer/vectorfield_viewer.html` — Three.js r128 Viewer (~7000 Zeilen), das **Template**
  (ohne Daten). EIN Template für beide Repos.
- `Viewer/export_vectorfield.py` — EIN Export für BEIDE Repos. Was exportiert wird, steht in
  der Liste **`DATASETS`** (pro Repo in `DATASETS_BY_REPO`): ein Eintrag pro Region
  (`name`, `run` — `None` = nur Sterne —, optional `stars`, `masses`, `mask_level`); alle
  landen in EINER Datei (s. „Mehrere Datensätze"). `REPO = "taurus"|"claude"` oben; CLI
  `python export_vectorfield.py [taurus|claude] [run]` = genau dieser eine Run.
  `python export_vectorfield.py batch` = Light-Versionen aller `BATCH_RUNS` nach `Viewer/Runs/`
  (s. „Export-Pipeline").
  - taurus: `Runs/<n>/results/last.pkl` + `Parameters/<n>.py`, repo-eigene simple_functions,
    eta-Rekonstruktion aus Posterior-Latents; gewichtete Residuen = Residuum/Katalogfehler
    (bewusst OHNE sigma_int). **Venv `TaurusVelocityField/.venv`.**
  - claude: `Runs/<n>/last.pkl` + `parameters_used.txt`, `Visualisation/simple_functions`,
    rv_used aus dem echten vfield-Datenlader; gewichtete Residuen mit
    σ_eff = √(σ_gaia² + σ_int² [+ σ_rv_jitter² auf rv]) wie in der Likelihood
    (inferierte Werte → Posterior-Mittel des jeweiligen Latents); eta (noch) nicht
    rekonstruiert (andere Latent-Struktur) → Felder leer, Viewer blendet sie aus.
    `mask_level` im DATASETS-Eintrag. **Venv `ClaudeVelocityField/.venv`.**
  - `mask_level`: DATASETS-Eintrag → `posterior_plotting.density_mask_level` → 0.001 (alte
    taurus-Parameterfiles haben die Sektion nicht immer).
  - **Alte taurus-Runs exportieren:** `Parameters/<n>.py` driftet von dem Run ab, den es
    erzeugt hat (s. Memory „Run-Config-Archäologie"). Bricht `apply_models` mit einem
    Broadcast-Fehler in `correlated_field`/`gauss_markov` ab, stimmt `zero_pad_pixels`
    nicht: die wahre Padding-Größe steht als Shape von `x_main_xi` im Checkpoint
    (`shape + zero_pad`). Passt die eta-Sternzahl nicht, überspringt der Export eta
    nur (Meldung „keine Strategie trifft Posterior") — der Rest bleibt gültig.
  - eta-Kandidaten (`_eta_from_posterior`, lazy in dieser Reihenfolge): `aktuell` =
    Parameterfile-Werte mit heutiger Formel, `legacy-2026` = ruwe 1.4 hart + buggy
    rv_integral, `legacy-ruwe-query` = buggy Formel + positionsabhängige Schwelle aus
    `gaiaunlimited` (`_ruwe_query_threshold`, Cache `saves/values/ruwe_threshold_gaia.npz`,
    an die source_ids gebunden). ⚠️ Die Schwelle IMMER aus dem übergebenen (schon per
    source_id umsortierten) Frame abfragen — `Data/Gaia.csv` hat eine andere Zeilenfolge
    als das Stern-CSV, und die fertige `ruwe_threshold.npy` im Taurus-Repo gehört zum
    Stern-CSV.
  - Chronos-Massen in beiden Modi per source_id aligned; Assets (local_bubble/dustmap npz)
    liegen in `Viewer/saves/values/` (Suchpfad prüft zusätzlich beide Repos).
  - Voxel-Format: pro Voxel `mass_density` (KDE-Massendichte) statt gebackenem `mask`-Bool;
    curl/div/std ÜBERALL (nicht mask-gestrippt); `meta.mask_level` = Default-Schwelle,
    der Viewer maskiert live (Slider). `meta.kde` (smooth=`KDE_SMOOTH`,
    origin/shape/distances/spacing) = das KDE-Rezept, mit dem der Viewer die Dichten
    selbst nachrechnet (s. „Mask-Sektion").
  - `meta.repo` = "T"/"C" + result_name → Viewer zeigt **"[T] final_run"** (HUD,
    Info-Modal, Footer); alte Exporte ohne meta.repo zeigen den nackten Namen.
- `Viewer/tests/make_test.py` + `run_tests.sh` — feste Test-Infrastruktur (s. u.).
- `Viewer/generate_local_bubble.py`, `sample_dustmap.py` (+ `L19_map_inner_final.fits`) —
  Asset-Generatoren (Pfade __file__-relativ, Output → `Viewer/saves/values/`).
- `Viewer/vectorfield_data.json` — JSON-Export für den Drag&Drop-Schnelltest.
- `Viewer/index.html` — Landing Page (GitHub Pages). Ganz oben „Current version" → die
  Root-Datei `vectorfield_viewer_data.html` (fortlaufender Stand, Mehrregionen-Viewer, ALLE
  Features inkl. Dustmap — User-Wunsch Okt 2026; jeder Export aktualisiert sie). Die
  Root-`_light.html` entsteht weiter, ist aber nicht mehr verlinkt. Darunter zwei Karten auf die
  EINGEFRORENE Thesis-Version `Runs/test_no_sigma_full.html` / `Runs/test_no_sigma_light.html`
  ([C] test_no_sigma; Okt. 2026 aus den Root-Dateien umbenannt, damit Template-Umbauten
  die Landing Page nicht verändern — NICHT überschreiben), unten „Other runs"
  aus `Viewer/Runs/`. Namensschema: `<run>_light.html`; **verlinkt wird dort nur die
  LIGHT-Version** (User-Entscheid) — die Wahl gibt es nur oben für den Hauptrun.
  **Wording auf der Seite (User-Wunsch Okt 2026): NIE „Full/Light", sondern „Compact"
  (= _light, empfohlen) und „Compact + dust map"** (= _full) — die Dustmap ist fremde
  Vergleichsdaten (Edenhofer 2024), nicht Teil der Arbeit. Dateinamen bleiben (eingefroren).
  Neuer Run: exportieren, Light-Datei nach `Runs/`, Eintrag ergänzen (Name, Pipeline-Tag,
  EIN beschreibender Satz, Link).
- `TaurusVelocityField/plot_data.py` ist Quelle für v_ref, sun_motion, pm/rv-Projektion
  (Details + Regeln in `../.claude/TaurusVelocityField.md`).

## Workflow (plan → edit → test → export)
0. **Plan zuerst** (bei nicht-trivialen Tasks): Teilschritte, betroffene Codestellen, Testweise.
   Mechanische Schritte (Export ausführen, Test-Matrix, PASS/FAIL melden) per Agent-Tool mit
   `model: sonnet` delegierbar; Design + Edits an der großen Datei bleiben im Hauptmodell.
   Mehrteilige User-Wünsche in EINER Session abarbeiten.
1. Änderungen im **Template** `Viewer/vectorfield_viewer.html` machen.
2. **Headless testen** mit `Viewer/tests/make_test.py` bzw. `bash Viewer/tests/run_tests.sh`
   (s. u.) — KEINE neue Harness pro Session; neue Checks als P()-Zeilen dort ergänzen.
   Mathematik zusätzlich in Python nachrechnen.
3. Export: `TaurusVelocityField/.venv/bin/python Viewer/export_vectorfield.py taurus` bzw.
   `ClaudeVelocityField/.venv/bin/python Viewer/export_vectorfield.py claude [result_name]`
   → erzeugt `Viewer/vectorfield_viewer_data.html` (~12–24 MB; ersetzt `/* __EMBEDDED_DATA__ */`;
   BEIDE Modi schreiben dieselbe Datei — das [T]/[C]-Tag im Viewer sagt, was drin ist).
   Kurzer Smoke-Test der echten Datei (Harness-Snippet anhängen, headless).
   Die Root-Dateien `vectorfield_viewer_data.html`/`_light.html` schreibt jeder Export neu;
   `_data.html` ist die „Current version" der Landing Page. **`Viewer/Runs/` ist das Archiv der
   BSc-Thesis-Aufnahmen** — alle dortigen Dateien bleiben eingefroren, `_guard_output()` im
   Export bricht ab, bevor er eine bestehende Datei dort überschreibt (auch `batch`). Die
   Thesis-Hauptversion liegt eingefroren unter `Runs/test_no_sigma_{full,light}.html`.
4. Ohne Export ist der Viewer leer; zum Schnelltest JSON per Drag&Drop laden.

## Effizienz-Regeln
- **Numerik gegenprüfen:** `tests/make_test.py` backt neben den Mini-Daten eine Brute-Force-
  Referenz-KDE (`_kde_reference` → `KDE_REF`, reines Python, gegen scipy verifiziert) ein; der
  Harness vergleicht die Viewer-KDE voxelweise damit. Neue Rechen-Features genauso absichern.
- **Feste Test-Infrastruktur:** `python3 tests/make_test.py` baut Mini-Datensatz + Diagnose-Harness
  nach `/mnt/c/Temp/vfvtest/test.html` (Verzeichnis ist DAUERHAFT, nicht löschen — Chrome-Profil
  `prof/` bleibt für localStorage-Roundtrips). Phasen per `?phase=N` (1 Funktionstests, 2 Save→
  Reload-Roundtrip, 3+ visuelle Checks, 8 = Marker-Formen `&glyph=…`, 9 = Raymarch-
  Smoke-Test mit Pixel-Readback: Dust beide Blendings + Threshold + Slice, Cloud-Volume beide
  Blendings, `&shot=cloud` lässt die Cloud fürs Bild an; Docstring hat die Chrome-Kommandos).
  - **Sektions-Filter:** die Phase-1-Blöcke sind `SEC('titel', () => {…})`-Sektionen;
    `bash tests/run_tests.sh <muster>[,<muster>…]` fährt NUR passende Sektionen (Substring)
    in einem WEGWERF-Profil (`prof_only`) — Schnellmodus fürs Iterieren an EINEM Feature.
    Unsektionierter Code zwischen den Blöcken ist SETUP und läuft immer; Restores auf die
    Baseline gehören auf diese Ebene, NICHT ans Ende einer Sektion (sonst fehlen sie beim
    Skippen). 0 Treffer = FAIL. Jede Sektion muss standalone grün sein (sonst fehlt ihr
    eigenes Setup — dann DAS fixen). Der Voll-Lauf (`run_tests.sh` ohne Argument, ~4 s)
    bleibt das Gate vor Abschluss.
  - **Visuelle Phasen:** das Plot-Fenster deckt die Bildmitte ab und verdeckt die Feld-Box —
    für 3D-Shots weglassen oder wegschieben.
- **Gezielt lesen:** aus der großen Datei nur relevante Zeilenbereiche (grep → Read offset/limit).
- **Allowlist:** `../.claude/settings.json` (Workspace) erlaubt den Standard-Workflow ohne Rückfragen; neue
  wiederkehrende Befehle dort ergänzen. **Permission-Pfad-Syntax:** absolute Pfade brauchen
  `//`-Präfix (`Edit(//home/...)`) — ein einzelner `/` heißt „relativ zur settings-Datei".
- **Agents:** eigenen Kontext für Suche/Exploration und mechanische Verifikation nutzen; Edits an
  der EINEN großen Datei nicht auf mehrere Agents verteilen (kalte Doppel-Reads kosten mehr).
- Diese Doc aktuell halten; überholte Abschnitte löschen (der Index `../.claude/CLAUDE.md` lädt
  in jede Session und verweist hierher — bei Viewer-Arbeit diese Datei zuerst LESEN).

## Koordinatensystem & Three.js
Heliozentrisch galaktisch-kartesisch (x,y,z in pc), Sonne bei (0,0,0), Taurus-Box im Zentrum.
**Three.js r128** — OrbitControls & CapsuleGeometry nicht verfügbar, kein ES-Module-Import
(alles global über CDN). Renderer läuft als WebGL2, wo verfügbar
(`renderer.capabilities.isWebGL2`); nur die Dustmap SETZT WebGL2 voraus.

## Performance-Regeln (einhalten!)
1. Dust-Volume (`G.dust`) und Local Bubble (`G.lbubble`) sind eigene THREE.Group, NICHT in
   G.objects. `buildObjects()` darf sie niemals anfassen.
2. **Regler wirken LIVE** (stehende User-Regel): Was ein Slider steuert, aktualisiert sich
   WÄHREND des Ziehens, nicht erst beim Loslassen — `oninput`, nie `onchange`. Der Weg
   dorthin ist ein möglichst billiger Update-Pfad: Uniform-Update ≫ Geometrie-Rebuild, und
   ein per rAF koalesziertes Rebuild (EINS pro Frame) statt eines pro Input-Event.
   Verzögern (Debounce bis zum Settle) ist die AUSNAHME und nur erlaubt, wenn ein einzelner
   Teilschritt das Frame-Budget auch koalesziert sprengt — dann NUR dieser Schritt, mit dem
   Grund als Kommentar an der Codestelle. Vorbild `setMaskLevel()`: Maske, Pfeile, Cloud,
   Colorbars und Plots laufen live per rAF, nur der RK4-Streamline-Retrace (180 ms) und der
   localStorage-Write (400 ms) hängen hinterher. Gilt auch für abgeleitete Anzeigen
   (Zahlen-Label, Statuszeilen, Colorbar-Enden) — sie sind Teil dessen, was der Regler
   steuert.
2b. **Slider ändern Bestehendes, statt neu zu bauen** (stehende User-Regel, Okt 2026): ein
   Live-Pfad baut Meshes/Materialien/Texturen NICHT bei jedem Schritt komplett neu, sondern
   verändert, was schon da ist — Reihenfolge der Wahl: Uniform setzen → Attribut-/Textur-
   Daten in place überschreiben (`needsUpdate`) → nur die Geometrie tauschen → erst zuletzt
   ein kompletter Neubau (nur bei Look-/Gitterwechsel). Besonders: **nie pro Event ein neues
   ShaderMaterial** (dispose des alten → three.js kompiliert das Programm neu, ~20 ms →
   Ruckeln; Fall Density-Cloud-Strength, s. Build-Funktionen). Beim Bau eines neuen Sliders
   den Pfad in einem Perf-Snippet mit echten Daten messen (Ziel: wenige ms pro Schritt).
3. `depthWrite:true` für Punkt-Shells, sonst verdecken sie Axis-Labels. `G.axes` renderOrder=200.
4. Lazy bauen: Layer werden nur konstruiert, wenn ihr Toggle an ist; Builder brechen bei
   verstecktem Layer nach dem Aufräumen ab; Reveal-Toggles bauen bei leerer Gruppe.
5. Streamlines nur tracen wenn sichtbar (RK4 dominiert Rebuilds; LSR/Taurus mäandern ~10× länger).
6. `disposeGroup()` (statt `clearGroup()`) in ALLEN Rebuild-Pfaden — sonst GPU-Leak. Shared
   `_glowTexCache`/`streamMaterial`/`dm._tex3d` ausgenommen.
7. Opacity-only Updates in place (`applyStarAlpha()`, Dust-Uniforms uOpacity/uGamma,
   `applyStreamAlpha()`).
8. Versteckte Partikel nicht ticken (`vis.streams`-Guard in `animate()`).

## Interface-Größe (`uiScale`, Okt 2026)
Menü-Text ist 7–10 CSS-px → auf DPR-1-Bildschirmen (großer Monitor, 100 % Skalierung)
pixelig. `applyUiScale()` setzt CSS `zoom` auf `<html>` (+ `--uiz`), State `uiScale`
(null = auto `_autoUiScale()` ≈ 1.5/DPR in 0.25-Stufen, 1…1.5; sonst `UI_SCALES`),
effektiv `UIZ`. Button `#uiscale-btn` („Aa …") im Header, `cycleUiScale` (Shift = zurück),
persistiert global (`uiScale`). Renderer-Pixelratio und Plot-Canvas-DPR × UIZ.
**⚠️ Regel für JEDEN Positionierungs-Code:** unter Zoom liefern getBoundingClientRect/
clientX/innerWidth VISUELLE px, `style.left`/offsetWidth sind LAYOUT-px → immer
`_bcr(el)`, `_cx(e)/_cy(e)`, `_vw()/_vh()` (liefern Layout-px), nie die Rohwerte; CSS-vh/vw
als `calc(… / var(--uiz))`. Nur reine Deltas (Kamera-Drehen `prevM`) bleiben roh.
Headless-Chrome hat DPR 1 → **die Tests laufen mit Auto-Zoom 150 %** (gewollt, prüft die
Helfer mit); Harness-Code, der Koordinaten an Viewer-Fns übergibt, nimmt ebenfalls `_bcr`.

## ⭐ Headless-Browser-Test via WINDOWS-CHROME
**Firefox-Headless ist KAPUTT** (Snap hängt endlos) — Windows-Chrome via WSL-Interop nutzen:
```
"/mnt/c/Program Files/Google/Chrome/Application/chrome.exe" --headless=new --disable-gpu \
  --user-data-dir="C:\\Temp\\vfvtest\\prof" --dump-dom \
  "file:///C:/Temp/vfvtest/test.html?phase=1" > /mnt/c/Temp/vfvtest/dom1.html
```
`--dump-dom` → PASS/FAIL-Liste aus `<div id="diag">`; `--screenshot="C:\\Temp\\vfvtest\\out.png"`
für visuelle Checks (PNG mit `Read` ansehen). Harness-Prinzip: Diagnose-`<script>` vor `</body>`,
ruft `initScene()` synchron, greift auf top-level `let`/`const` zu (gleicher globaler Scope).
- **Timing:** Screenshot feuert nach `load` → alles SYNCHRON. Mit `--virtual-time-budget=<ms>`
  laufen auch setTimeout/rAF — nötig, um NACH dem Auto-Init (`setTimeout(initScene,10)`) zu agieren
  (das sonst Harness-Setup wie Kamera/Suchmarker überschreibt).
- **Kamera:** `camTheta/camPhi/camDist/target` wirken erst nach `camUpdate()`.
- **Raycast:** nach Build erst `scene.updateMatrixWorld(true)`.
- **Pixel-Readback:** `renderer.getContext().readPixels` nach `renderer.render()` funktioniert
  (preserveDrawingBuffer). ⚠️ Additive Layer (Sonnen-Glow, Sterne) sättigen die Bildmitte auf
  255 — Diff-basierte Checks (Layer an/aus) müssen das Zentrum vorher leerräumen, sonst diff=0.
- **localStorage:** `file://` skopiert pro VOLLEM Dateipfad; Roundtrip = dieselbe Datei + dasselbe
  Profil. **⚠️ Zahlen aus einem ECHTEN Export immer mit FRISCHEM `--user-data-dir` messen:** das
  Dauerprofil trägt die Settings der Harness-Läufe (z. B. `maskKdeFactor=0.35`), und die
  Live-KDE rechnet dann mit fremder Bandbreite — sah wie ein 10-%-Fehler in Masse/E_kin aus,
  war reine Profilverschmutzung. Mit sauberem Profil trifft der Viewer plot_data exakt
  (Peak-Dichten 0.022651/0.086940, Maske 1817 Voxel, E_kin 2.821e39 J bei test_no_sigma).
  **Neue Settings-Keys IMMER als Save→Reload-Roundtrip testen** (leeres localStorage übersieht
  TDZ-Fehler).
- **⚠️ `alert()`/`confirm()` blockiert Headless-Chrome endgültig** (kein Dump, auch nicht
  mit `--timeout`, der Lauf hängt) — Tests, die einen Pfad mit möglichem alert berühren,
  stubben `window.alert`. Hängt ein Lauf: NUR die Test-Chromes beenden (PowerShell
  `Get-CimInstance Win32_Process … CommandLine -like '*vfvtest*' | Stop-Process`), **NIE
  `taskkill /IM chrome.exe`** — das schließt auch den Chrome des Users. Hängende Instanzen
  halten sonst das Profil gesperrt → Folgeläufe liefern leere Dumps.
- **Testdaten-Fallen:** `meta.extent` CENTER-basiert (erste/letzte Voxel-Zentren) — kantenbasiert
  verschiebt `maskAt()` um ½ Voxel und Streamlines sterben. Voxel brauchen `ix/iy/iz`. Die fixe
  Diagnose-Box kann als weißes Geister-Rechteck doppelt-compositen — ignorieren.
- **Harness-Falle:** ohne `?phase=` läuft phase 1 als Default — eigene Visual-Snippets müssen
  `#diag` entfernen / Fensterzustand explizit setzen. Einzelne Test-Blöcke tauschen
  `DATA.reference_objects` aus — `_bakedRefObj` (Anfang phase 1) restauriert das Original.
  Das DAUERPROFIL restauriert die am Ende des LETZTEN phase-1-Laufs gespeicherten Settings
  (z. B. Plot-Typ scatter/power) — phase 1 forciert deshalb früh `setPlotType('hist',…)`;
  neue Tests ebenso deterministisch aufsetzen, nie auf Restore-Zustand bauen.
  Canvas speichert `lineWidth` als float32 — Vergleiche mit Toleranz, nie `===`.

## Viewer-Architektur (Wegweiser)

### Gruppen
`G.arrows .streams .stars .cloud .objects .dust .lbubble`, `G.box` (renderOrder 100), `G.axes` (200).
`DATA.voxels` = Gitterdaten je Zelle (keine Voxel-Würfel-Visualisierung).

### Build-Funktionen
`buildAll()` (Reihenfolge: `refreshLocalBubbleSlider()`+`refreshDustmapSection()` FRÜH, schwere
Builds in try/catch), `buildObjects()`, `buildDustCloud()`/`buildLocalBubble()`
(eigene Gruppen; Slider via Shader-Uniforms), `buildCloud()` (density frame-unabhängig,
energy_density live), `buildArrows()`, `buildStreamlines()`, `buildStars()`.
- **Density-Cloud „Render as" Volume|Points** (`cloudRender`, per Satz, Default 'volume',
  Okt 2026): Volume = `_cloudVolumeMesh()` — RGBA-`DataTexture3D` (ein Texel pro Voxel,
  R = geformte Dichte frac^gamma wie die Sprites, G = R·Grau-Flag premultipliziert) +
  1D-Colormap-Textur; Raymarcher wie die Dustmap (½ Voxel/Schritt, ≤256 Samples, Farbe aus
  der INTERPOLIERTEN Dichte, `CLOUD_SIGMA`/Voxel). `cloudPoints` hält BEIDE Looks (Points
  oder Mesh) — Toggle/Style-Swap/Intensity (`uOpacity`) bleiben ein Pfad. **Rebuilds
  verwenden Objekt + Material WIEDER** (Volume: `_fillCloudVolume`/`_fillCloudCmap`
  schreiben die Texel in place; Points: nur Geometrie tauschen); `_disposeCloud()` nur bei
  Look- oder Gitterwechsel (`userData.sig`). Grund: neues ShaderMaterial + dispose des
  alten → three.js verwirft das Programm (Refcount 0) und kompiliert neu, ~20 ms pro
  Schritt → Strength-Slider ruckelte (jetzt ~1.5 ms). Strength ist rAF-koalesziert
  (`_scheduleCloudRebuild`/`_cloudRafId`, in `_flushDeferred`). Ohne WebGL2 → Points.
  **Allgemein: ShaderMaterials in Live-Pfaden nie pro Event neu bauen.**
  **„Over axes"** (`cloudCoverAxes`, per Satz, Default an, nur Volume): `_applyCloudBlend()`
  setzt die Cloud-GRUPPE auf renderOrder 250 (> Box 100/Achsen 200 — in r128 zählt die
  Gruppen-renderOrder vor der des Objekts) und premultiplied-over-Blending (Custom ONE /
  ONE_MINUS_SRC_ALPHA, Shader-Uniform `uPremul`) in BEIDEN Styles → die Wolke absorbiert
  Box/Achsen dahinter; über schwarzem Grund identisch zum additiven Glow. Ohne Depth-Test
  verdeckt sie Achsenstücke VOR der Wolke genauso (gleicher Trade-off wie Dust). Aus/Points:
  renderOrder 3 + `glowBlending()`. Läuft bei jedem Build und im Style-Swap (nur
  Blending/Uniforms, kein Programmwechsel).
- Density-Cloud: EIN `cloudStrength`-Slider (ersetzt Point size/Glow gamma/Cutoff):
  size ∝ √strength, gamma = 0.6/strength (in `buildCloud`); fester Floor 0.01 statt Cutoff
  (Sichtbarkeits-Cut macht der Colorbar-Regler). Legacy-Saves: params-Setter leitet
  `cloudStrength` aus altem `cloudGamma` ab.
- Der zweite Cloud-Slider heißt im UI **„Intensity"** (0–1.5), Param-Key bleibt `cloudAlpha`
  (Saves!). Es ist KEINE Opacity: Sprite-Alpha = `glow(radial) × dichte^gamma × cloudAlpha`,
  fast überall weit unter 1 → Werte >1 heben v.a. die schwachen Außenbereiche an.
- Local-Bubble-Punktzahl je Stufe: `lbubblePointCount(nside)` (liest `levels_q16`, base64
  3×uint16/Punkt → /6 Bytes; Legacy-`levels`-Fallback).
- Sonne: `coreDot`-Radius = `min(spacing)·0.18` (= Star-Dot-Radius), `glowSprite` dazu.
- **Marker-Form (Button `#arrow-glyph-btn` neben „Show as"):** `fieldVectorGlyph`
  ('arrow'|'cone') / `fieldScalarGlyph` ('cross'|'diamond'), beide im STATE-Block, persistiert als
  EIN Blob `fieldGlyph`. `arrowIsCross()` entscheidet Vektor-vs-Skalar-MODUS, `fieldGlyph()`
  liefert die Form des aktiven Modus; `toggleFieldGlyph()` schaltet um, `_syncGlyphButton()`
  beschriftet den Button (Aufruf in `refreshComponentDropdown` UND `setArrowComponent`).
  In `buildArrows`: cone = EINE volle ConeGeometry ohne Schaft (`arrowShaftMesh=null`),
  diamond = `OctahedronGeometry(0.5)`; Skalen `markScale` (cross 1.15 / diamond 0.8).
  Die „Show as"-Zeile ist IMMER sichtbar; bei nur einer Option (divergence) wird nur das
  `<select>` versteckt und das Label heißt „Marker".

### Dustmap = volumetrisches Raymarching (Aug 2026)
`buildDustCloud()` baut EIN Box-Mesh (`dustVolume`) mit Raymarching-Shader über das
q8-Gitter — keine Punktwolke mehr (weiche Wolken-Optik, kein Moiré, Renderlast skaliert
mit Bildschirmpixeln statt Punktzahl).
- Das dichte Uint8-Gitter (`reference_objects.dustmap.q8`, s. Export-Pipeline) wird als
  `THREE.DataTexture3D` hochgeladen (RedFormat/UnsignedByte, LinearFilter, unpackAlignment 1)
  und wie die dekodierten Bytes auf dem dustmap-Objekt gecached (`dm._tex3d`, `dm._q8`,
  `dm._labelPos`) — Layer-Toggles re-uploaden nichts.
- **Achsen-Mapping:** q8 ist C-Order über (ix,iy,iz) mit iz am schnellsten → Textur
  (width,height,depth) = (nz,ny,nx), der Shader sampelt mit `.zyx`-Swizzle. Volumen-Box =
  Voxel-ZELLEN um die Voxel-Zentren (origin−spacing/2 … origin+(n−0.5)·spacing).
- **Shader (GLSL3, braucht WebGL2 für sampler3D):** `glslVersion: THREE.GLSL3`;
  Slab-Test Ray↔AABB (Kamera drinnen: t0=0), front-to-back Emission/Absorption,
  1 Voxel pro Schritt, max 160 Samples, gejitterter Startpunkt gegen Banding, early-out
  bei Transmittanz <0.02. Dequantisierung im Shader: d = max(v·255−1, 0)/254
  (log-normierte Dichte); Extinktion σ = d^uGamma · uOpacity · `DUST_SIGMA_SCALE`
  (String-Konstante direkt überm Builder, wird als GLSL-Literal interpoliert).
- **Blending:** folgt `glowBlending()` — additiv (dark) gibt premultipliziertes
  `vec4(uColor·acc, 1)`, normal (light) `vec4(acc/α, α)`; der Zweig hängt an der
  Uniform `uAdditive`, die `setViewerStyle` zusammen mit `material.blending` in place
  swappt (kein Rebuild).
- **depthTest:false + side:BackSide + frustumCulled:false:** die Box umschließt die ganze
  Szene; mit Depth-Test würde jedes opake Objekt in der Box ein Loch in den Staub stanzen
  (BackSide-Fragmente liegen an der HINTEREN Boxwand). Dafür leuchtet der Staub additiv
  auch „vor" Objekten — bewusster Trade-off ohne Depth-Compositing.
- Slider: `dustOpacity` (globaler Dichte-Multiplikator, **LOG-Regler** 0 = aus, 1…1000 =
  0.001…1 über `dustOpacityFromSlider/ToSlider`, Exakteingabe via `setDustOpacityExact`;
  linear waren nur die ersten Prozent nutzbar), `dustCut` („Dust threshold" 0–0.9: Shader
  zieht die log-Dichte ab und skaliert neu → diffuser Staub verschwindet, gegen
  „überfüllt") + `dustGamma` („Dust contrast", 0–5) — alle reine Uniform-Updates in
  `setObjParam` (Map key→Uniform, early return, Save debounced), persistiert im
  `objParams`-Blob. Defaults 0.05 / 0 / 2.5 (JS = HTML; vorher stand JS auf 0.5/1.0).
- **Slice (Okt 2026):** nur eine Scheibe der Dustmap sichtbar — `objParams.dustSliceOn/
  dustSliceAxis ('x'|'y'|'z')/dustSlicePos (pc heliozentrisch, null = Mitte von
  `sceneExtent()`)/dustSliceWidth` (im objParams-Blob persistiert). REINES Uniform-Update:
  der Shader schneidet den Strahl mit der beschnittenen Box `uClipMin/uClipMax`, die
  Texturkoordinaten nutzen weiter `uBoxMin/uBoxMax` → Ziehen ohne Rebuild. `_applyDustSlice()`
  (auch am Ende von `buildDustCloud`) setzt Uniforms + den Rahmen `dustSliceOutline`
  (Einheitswürfel-Kanten, nur scale/position). `dustSliceRange()` klemmt Breite ≥ 1 Voxel und
  Mitte in die Box. UI `_syncDustSliceUI(skipEl)` — Slider-Bereiche brauchen die Daten, darum
  zusätzlich aus `refreshDustmapSection()`; Achsenwechsel setzt die Position auf null.
  Zeilen (User-Wunsch): Position → Width → Sweep speed → eigene Zeile mit Toggle „▶ Sweep“/
  „■ Stop“; KEIN ⟲-Reset-Knopf für die Position. „Border“-Toggle in der Slice-Zeile
  (`objParams.dustSliceBorder`, Default an) blendet nur den Rahmen aus.
  Grid-Helfer `_dustGrid(dm)`/`_dustBounds(dm)` (q8 + Legacy). Gedacht als Vorlage für ein
  späteres Feld-Slicing.
  **▶ Sweep** (`toggleDustSweep`/`stopDustSweep`, Button `#dust-slice-sweep`): Mitte läuft
  EINMAL Start → oberes Ende → unteres Ende → Start (`_dustSweepPos`), innerhalb
  [lo+w/2, hi−w/2]; zeitbasiert aus `animate()` (`_tickDustSweep(now)`), pro Frame nur
  Uniforms/Rahmen/Labels, Save erst am Ende. `objParams.dustSweepSpeed` (pc/s, Slider;
  Wechsel mitten im Lauf verankert die Uhr neu). Stoppt bei Positions-Slider, Achse,
  Slice aus. **`_dustSweep` steht im STATE-Block** — `animate()` läuft schon beim Parse
  einmal synchron (TDZ). Headless liefert unter `--virtual-time-budget` kaum rAF-Frames →
  Sweep im Test über `_tickDustSweep(t)` bzw. einen manuellen `animate()`-Aufruf prüfen.
- Kein WebGL2 → `refreshDustmapSection()` versteckt die ganze Dust-Sektion,
  `buildDustCloud` bricht mit console.warn ab.
- **Legacy xyz/val** (alte Drag&Drop-JSONs): `_dustGridFromLegacy()` voxelisiert einmalig
  auf dasselbe Gitterformat (`dm._legacyGrid`) — der Raymarcher ist der EINZIGE Renderpfad.
- Label am dichtesten Voxel, weiter in G.dust (s. Label-Regel bei „Bekannte Bugs").
- Tests: P()-Zeilen in phase 1 (Decode, Texturachsen, Bounds, Uniform-Slider, Legacy-
  Voxelisierung) + **Phase 9** = Render-Smoke-Test mit Pixel-Readback in BEIDEN
  Blending-Modi — der Shader kompiliert erst beim ersten echten Render, phase 1 fängt
  Compile-Fehler NICHT.

### Reference Frame (Kernkonzept)
Vier Modi: raw/taurus/lsr/custom (`refFrameMode`, `customRefVec`). Export liefert **nur rohe**
`vx/vy/vz`; jeder Frame = Subtraktion EINES festen 3-Vektors (`activeRefVec()`). Ein Codepfad
für alle Frames (`vField()`/`effComponent()`). `projectToObsFrame()` → {pmra,pmdec,rv} (feste
GAL2ICRS-Rotation + Tangentialprojektion, `PM_K=4.740470463533`; <1e-9 gg. astropy verifiziert).
`scanObsRange()`/`_magRange()` — live Min/Max, gecached per `_rangeSig()` (Frame + Mask-Level),
Reset in `buildAll()`. Curl/Div/Std/ρ-Autos: live über die AKTUELLE Maske via
`_derivedRange(kind)` (Cache per Level; `meta.*_min/max` nur Leermasken-Fallback).
Magnitude-Range: echtes Min/Max in der Maske (kein Perzentil). **Feld-Marker sind IMMER
mask-only** (`maskOnly` existiert nicht mehr).

### Mask-Sektion: Cut-Level + Live-KDE
**EIGENE Sidebar-Sektion `#section-mask`** (zwischen Reference Frame und Field) — sie hält
alles, was die Maske definiert: Cut-Level, KDE-Bandbreite, Sternauswahl.

**Cut-Level.** `applyMaskLevel()` (früh in `initScene`) setzt `v.mask = mass_density >
effMaskLevel()` und `v._fixedMask` (= Default-Level). State `maskLevel` (STATE-Block, TDZ!;
null = Default, persistiert als ABSOLUTER Wert; `effMaskLevel()` KLEMMT auf den Slider-Bereich).
EIN Slider `#mask-level` (`.mask-level-row`), log-uniform über `MASK_DEC_DOWN`/`MASK_DEC_UP`
Dekaden = **Default/100…Default·10**, Default bei t=2/3 → HTML `value="667"`.
**`setMaskLevel(t,el)` ist LIVE**: rAF-koalesziert ein Rebuild pro Frame (`_maskRafId`),
`_applyMaskChange(skipEl, deferStreams)` macht Maske + Caches
(`_magCache/_obsCache/_energyCache/_psCache/_derivedCache`) + buildLookup/Arrows/Cloud +
Colorbars + Plots. Bewusst NICHT pro Frame: `buildStreamlines` (debounced 180 ms) und
`saveSettings` (debounced 400 ms; `resetMaskLevel()` speichert selbst). `_syncMaskSliders`
lässt den Regler unter dem Finger in Ruhe; **Label = nur das Level**, die Voxelzahl steht in
der Statuszeile `#mask-kde-info` (`_syncMaskInfo()`). ⟲ = `resetMaskLevel()`.
**Exakteingabe:** `wireSliderTyping()` kann pro Zeile über `data-type-set`/`data-type-get`
umgebogen werden (hier `setMaskLevelExact`/`_maskLevelTypeValue`) — der generische Pfad rechnet
die getippte Zahl auf die Regler-Position um und machte aus jedem kleinen Wert Slider-Schritt 0.

**Live-KDE.** `meta.kde = {smooth, origin, shape, distances, spacing}` ist das Rezept der
Dichten: `mass_density` = massen-gewichtete Gauß-KDE der Sternpositionen, `density` = ungewichtet.
`computeKdeDensity(stars, weighted, bwOverride)` rechnet BEIDE im Browser nach — 1:1 wie
`scipy.stats.gaussian_kde(values, weights, bw_method=f)(grid)·Σw` (auf 1e-9 verifiziert).
Gewichtete Kovarianz = `np.cov(aweights=w, bias=False)`, Faktor `_kdeFactor()`, 3×3-Inverse
geschlossen. Performance: pro Stern nur das Gitterfenster im `KDE_CUT`=7-Mahalanobis-Radius,
entlang z per Exponential-REKURSION statt exp() je Voxel → **15 ms für 557 Sterne × 25000
Voxel**.
- **⚠️ Das KDE-Gitter ist NICHT zwingend das Voxelgitter:** `meta.kde.spacing` trägt die echte
  Schrittweite (s. Export-Pipeline, Bugfix-Absatz); ohne den Key gilt die alte inklusive
  mgrid-Formel als Fallback für bereits gebackene Dateien.
- State (persistiert als EIN Blob `maskKde`): `maskKdeFactor`, `maskUseGroups`,
  `maskDensityKind`. Bandbreite = NUR der Live-Slider mit ⟲ auf `meta.kde.smooth`
  (`resetMaskKdeFactor()`); `maskKdeMethod` existiert nicht mehr, Alt-Saves mit
  `method:'export'|'scott'|'silverman'` verwerfen ihren Faktor. `kdeIsDefault()` (Faktor =
  Export-Wert UND keine Gruppenkopplung) stellt die in `initScene` gesicherten Werte
  (`v._mdBaked`/`v._dnBaked`) bitgleich wieder her.
- `applyKdeChange(live)`: `live` (Bandbreiten-Slider) = rAF-koalesziert, sonst synchron;
  `_kdeApply()` = recompute + `_energyCache`/`_ekinCache` invalidieren + `_applyMaskChange()`.
- **„Apply to mask"** (`maskUseGroups`) koppelt die KDE an den Gruppenfilter: `kdeStars()` =
  `starGroupPred()`-gefilterte Sterne (bewusst NICHT die Display-Maske All/HasRV/Used).
  <4 Sterne → `recomputeMaskDensity()` gibt false, Dichte bleibt stehen, `_kdeFail` färbt
  die Statuszeile.
- Gruppen-Button `#mask-groups-btn` = DRITTER Einstieg ins geteilte `#group-pop`.
- **Maskenquelle** (`maskDensityKind` = 'mass'|'stars'): Schwelle wahlweise auf der
  massengewichteten KDE (M☉/pc³) oder der Sterndichte (stars/pc³); jede Quelle hält ihr
  eigenes Level (`maskLevelMass`/`maskLevelStars`); der 'stars'-Default wird aus
  `meta.mask_level` mit dem Verhältnis der Feld-PEAKS skaliert. `v._fixedMask` bleibt
  immer massengewichtet.

Die Density-**Cloud ist mask-gefiltert** (`if(!v.mask) return` in `buildCloud`).
Colorbar-Autos folgen der Maske, manuelle min/max-Overrides bleiben unangetastet.
Alte Exporte (gebackenes `mask`): Sektion versteckt; ohne `meta.kde`: nur der Cut-Level-Slider.
**E_kin-Integral ohne jede Maske** (User-Entscheid Aug 2026): `kineticEnergyIntegral()`
summiert über ALLE Voxel mit ρ = `mass_density ?? density` — jede Maske schneidet Sternmasse
weg, die Zahl hinge sonst an der Schwelle. `energyDensity()`/`_energyRange()` nutzen dieselbe
ρ-Quelle, folgen aber der aktuellen Maske.

### 3D-Styles (`VIEWER_STYLES`)
8 Presets (midnight/daylight = Ur-Themes, dazu slate/blueprint/contrast/paper/solarized/
graphite). Ein Preset färbt den Render — `bg`, `ax`/`axl` (Achse+Label je x/y/z), `box`, `txt`
(Default der Text-Sprites) — UND optional per `ui:{CSS-Var:Wert}` das Interface:
`setViewerStyle(id)` setzt `.dark` (aus `dark:`) und schreibt die Overrides INLINE auf `:root`,
vorher werden alle `VIEWER_STYLE_VARS` entfernt. `isDark` bleibt als Flag (glowBlending,
Screenshot-Panel lesen es), `toggleDarkMode()` ist nur Legacy-Shim. State `viewerStyle`
(STATE-Block, TDZ!) + Legacy-Key `isDark` — Tabellenreihenfolge: `isDark` zuerst, `viewerStyle`
danach, damit der neue Key gewinnt.
UI: Button `#vstyle-btn` im Sidebar-Header (nur Preset-Name), Liste `#vstyle-pop` (gleiches
Widget/CSS wie `#style-pop` der Plots). Farbvorschau = `_styleSwatches(cols)` — nur in den
LISTEN. **Preset `custom` = das EINZIGE veränderliche:** Editor in der Liste
(`renderViewerStylePop` hängt `.vstyle-edit`-Block an: je eine Swatch-Zeile pro
`VSTYLE_EDIT_ROWS` = bg/ax0/ax1/ax2/box/txt + Dark-Light-Toggle). Swatches öffnen den
GETEILTEN Farbwähler mit Target `vs-<key>` (→ `_setCustomStyleColor`, minimaler Refresh, weil
der Picker pro Drag-Frame feuert). `axl` wird aus `ax` abgeleitet (`_axLabelColor`).
`_seedCustomStyle(activeId)` beim ERSTEN Wechsel auf custom (`customStyleEdited`-Flag).
Persistenz: Blob `viewerStyleCustom` — im SETTINGS_TABLE VOR `viewerStyle`, sonst restauriert
`setViewerStyle('custom')` die Seed-Farben. `#vstyle-pop` bleibt bei offenem Picker offen
(Outside-Click-Ausnahme `#color-picker-pop`). **2D- und 3D-Style sind entkoppelt** (User-Wunsch);
nur ein Plot auf 'theme' folgt der Chrome-Tönung. Screenshot-/Video-Colorbar-Streifen nimmt
`activeViewerStyle().bg` + `--text`/`--border2`.

### Colorbar Min/Max-Overrides
`colorMinOverride`/`colorMaxOverride = {field, cloud, star, stream}` (null = auto). Zwei
Zahlenfelder + „Auto" + ⇄ (`switchColorRange()`, min>max invertiert sauber) + **⤓**
(`adoptCbFilterRange(layer)`: übernimmt die Werte unter den Colorbar-Slider-Reglern als
min/max und setzt die Regler auf voll). Setter: `setColorOverride()` → `applyColorOverride()`.
Signed-Felder: nur-Max hält 0 zentriert `[-m,m]`. `setStarColorField()` setzt den
star-Override auf Auto zurück. Markup generiert: `buildOverrideRows` (Template
`.cb-minmax[data-cbl]`), Colormap-Selects aus `populateColormapSelects()`/`COLORMAPS` —
beide IIFEs laufen beim Parse VOR `loadSettings()`.
**2D-Plots haben dasselbe:** `PLOT_STATE[w].cMin/cMax` (null = auto), Zeile `#{p}-cminmax-row`
(in der `#{p}-crange`-Colorbar-Spalte), Fns `setPlotColorOverride/resetPlotColorOverride/
switchPlotColorRange/adoptPlotColorRange/effectivePlotColorRange/_syncPlotOverrideInputs`;
greift in `drawDataPlot` auf `cmn/cmx`, NICHT auf die Punktauswahl. Persistiert in
`plot2d`/`fieldPlot`.
**Scatter-Achsen-Ranges:** `PLOT_STATE[w].axOv = {xmn,xmx,ymn,ymx}` (null = auto). UI =
⋯-Box `#{p}-axrange-x/y` in jeder Achsenzeile (nur Scatter; zeigt aktiven Override als
„mn–mx" + `.on`), öffnet das geteilte `#axrange-pop` (min/max-Felder; ↑/↓/Tab wechseln,
ENTER übernimmt BEIDE, Esc verwirft). Fns `toggleAxRangePop/closeAxRangePop/_axrangeCommit/
_axrangeClear/_syncPlotAxisInputs/onPlotAxisFieldChange`; `_axrangeTarget` im STATE-Block.
Zusätzlich ⟲ `#{p}-axreset-x/y` links vom Achsen-Dropdown: `resetPlotAxis(axis,w)` leert
axOv + log + flip (x in hist auch `range`). Overrides ersetzen die GEPADDETEN Auto-Enden
exakt; min>max wird normalisiert; Zoom/Pan (`view`) liegt obendrauf, ⟲/Doppelklick kehrt zu
den Overrides zurück (nicht zu auto). Persistiert (`axOv`).

### Interaktive Colorbar-Filter (Field/Stream/Cloud-Sidebar, Stern-3D, 2D-Plots)
Zwei ziehbare Regler (Fraktionen t0/t1) filtern angezeigte Objekte; **hidden|greyed**-Toggle.
Farbskala immer LINEAR (Log lebt nur auf 2D-Plot-ACHSEN). Sub-Ranges Session-only, gray-Flags
persistiert (`cbFilterGray`, `starColorClipGray`, `plotColorGray`, `fieldPlot.cGray`).
- **Generisch (Sidebar):** `CB_FILTERS`+`cbFilter` (STATE-Block, TDZ!), Fns `cbFilterActive/
  cbFilterInSel/drawCbFilterHandles/toggleCbFilterGray/resetCbFilterSel/wireCbFilter`.
- **Filter in den Buildern:** `buildArrows` (`fv.scalar ?? fv.mag`), `buildCloud` (`def.getVal`).
- **Streamlines OHNE Re-Trace:** statischer Modus traced immer die volle Maske; Seed-Speed als
  Per-Vertex-Attribut `vSeed` + `ArrowHelper.userData.seedMag/origCol`. Shader (`STREAM_FRAG`)
  filtert über Uniforms `uFiltLo/uFiltHi/uFiltGrey` — Slider-Ziehen ruft nur
  `_applyStreamCbFilter()`, NICHT `buildStreamlines`. Animierter Modus kann das nicht
  (InstancedMesh) → filtert Seeds beim Tracen vor (`animExclude`) und rebuildet. Enges
  Fenster zeigt im statischen Modus WENIGER Linien (kein Nachseeden) — gewollt.
- **3D-Sterne:** `starColorSel{t0,t1}`, Overlay `#star-cb-handles`, Filter in `buildStars()`+
  `buildStarVectorArrows()`. **2D-Plots:** `PLOT_STATE[w].cSel/cGray/cAx`, Block `#{p}-crange`,
  Drag-Wiring `_wirePlotCbar(w)`.
- **⚠️ Objekte OHNE Wert (null) fasst der Range-Filter NIE an** — sie haben keine Fraktion
  auf der Skala. Ihre Sichtbarkeit steuert allein der **∅-Toggle** neben „Color by"
  (`starShowNoData` 3D / `PLOT_STATE[w].cNoData` 2D, beide persistiert, Default = anzeigen).

### Sterne
- `buildStars()` (Dots) / `buildStarVectorArrows()` (Geschwindigkeits-Pfeile). Display-Maske
  `starDisplayMask` (All/HasRV/Used) via `starMaskPred(which)` — gilt für Dots UND Pfeile.
  `effectiveColorRange('star')` und `getAvailableColorbars()` müssen dieselbe Maske anwenden
  wie die Builder, sonst weicht die gebackene Range ab.
- **Stern-Display-Modus (EIN Zyklus-Button `#star-vec-mode-btn`, `cycleStarVectorMode`):** State
  `starVectorMode` = 'dots'|'uvw'|'pm' (STATE-Block, TDZ!, persistiert). `starVectorsOn()` =
  `!== 'dots'`; `setStarVectorMode(m)` (baut+synct), `_applyStarVectorModeUI()` (Button/Zeilen,
  KEIN Picker-Zugriff → restore-safe). Legacy-Saves migriert `loadSettings`
  (`showStarVectors`+`starVectorSource` → `starVectorMode`). **uvw** = volle U/V/W (braucht rv),
  **pm** = reine PM-Tangential-Geschwindigkeit (Export-Felder `U_pm/V_pm/W_pm`, rv=0 im
  ICRS→Gal-Transform; `_starVecFields()` liefert Feldnamen + Label je Modus). Marker-Form =
  eigener Toggle `starVectorGlyph`/`#star-vec-glyph-btn` in eigener Zeile `#star-vec-shape-row`
  — dieselbe Cone-Logik wie die Feld-Pfeile.
- Rand um Dots: Inverted-Hull-InstancedMesh (BackSide, ×1.22, `raycast=noop`); nur bei voller
  Opacity (`applyStarAlpha()` versteckt ihn beim Faden).
- Verblasste Dots tragen `userData.alphaCap` (0.14 = out-of-range grau, 0.35 = kein Wert grau);
  `applyStarAlpha()` respektiert den Cap. Rand nur für voll gefärbte Dots.
- „Color by": `starColorField`, Gruppen `STAR_FIELD_GROUPS`, Labels `STAR_FIELD_LABELS`.
  Sichtbarkeit über `STAR_3D_COLOR_EXCLUDE` (UVW/Photometrie/mass_err und x/y/z nur 2D) und
  `STAR_AXIS_EXCLUDE` (`{rv_used}`); `starNumericFields(axisOnly,for3d,cat)` filtert.
  Restore-Validierung fällt bei unbekanntem Feld auf 'none'; `_legacyStarFields` migriert
  alte Namen. Sternpositionen x/y/z [pc] = Gruppe „Position" — 2D-Achsen + 2D-Farbe,
  NICHT 3D-Farbe.
  - **Kategorische Farbfelder (`STAR_CAT_FIELDS` = `name_luhman`, `name_sigma`; Gruppe
    „Membership"):** Wert ist ein Gruppen-NAME. Farben aus `STAR_CAT_PALETTE` (24 Einträge;
    Reihenfolge = Gruppengröße absteigend über ALLE Sterne, damit Maske/Filter die Farben nie
    umwerfen). Statt Colorbar eine reine Legende `#star-cat-row`/`#star-cat-chips`
    (`renderStarCatChips`, `starCatInfo/starCatColor/starCatCounts`); Ein-/Ausblenden macht
    der Gruppenfilter, NICHT das Farbfeld. `_starCmapOn()` blendet die Colormap-Zeile aus.
    **`STAR_CAT_FIELDS`, `isStarCatField`, `_starCatCache` stehen im STATE-Block** (TDZ-Falle,
    war real: `_applyStarVectorModeUI()` läuft aus `loadSettings()`). Überall sonst
    ausgeschlossen (Plot-Achsen, 2D-Farbe, Ranges): nur `populateStarDropdown` übergibt
    `cat=true`. Export: `_cat()` mappt '-' → None.
  - **Gruppenfilter „Star groups" (`#group-pop`):** EIN floatendes Fenster, geöffnet von
    `#star-groups-btn` (Stars-Sektion), `#plot-groups-btn` (Star-Plot-Fenster) UND
    `#mask-groups-btn` (`.grp-list` scrollt). State `starGroupField` + `starGroupHidden{field→Set}`
    (gespeichert werden die AUSGEBLENDETEN Namen, damit neue Gruppen per Default sichtbar
    sind; ohne Gruppe = Sentinel `NO_GROUP`). **Der Filter hängt in `starMaskPred()`**
    (`starGroupPred`) — dadurch greifen 3D-Dots, Vektoren, beide 2D-Plots, Counts und
    Auto-Ranges in einem Schritt (mit „Apply to mask" auch die KDE). Fns
    `toggleGroupPop/closeGroupPop/setStarGroupField/toggleStarGroup/setAllStarGroups/
    renderGroupPop/_groupRow/_syncGroupButtons/_applyGroupFilter`. Persistiert.
  - **Eigene Gruppen (`name_custom`):** `customGroups = [{name, color, ids}]` (STATE-Block,
    persistiert) wird von `applyCustomGroups()` als `s.name_custom` auf die Sterne
    GESCHRIEBEN — ab da normales kategorisches Feld. **Gruppen dürfen ÜBERLAPPEN:**
    `s._customAll` = ALLE Gruppen des Sterns, `s.name_custom` = die neueste (eine
    Farbe/Legende pro Stern). `starGroupPred()` hat für `name_custom` den Zweig „sichtbar,
    solange IRGENDEINE seiner Gruppen an ist", `starCatCounts()` zählt jede Mitgliedschaft
    (Zeilensummen > Sternzahl gewollt). `starCatInfo('name_custom')` nimmt Reihenfolge und
    Farbe aus `customGroups` (Cache-Reset per `delete _starCatCache['name_custom']`);
    `starGroupFields()` bietet den Tab IMMER an. `customGroupsChanged()` = der EINE
    Sammel-Refresh (inkl. `populateStarDropdown`). Umbenennen/Löschen nur im Group-Fenster
    (`_groupRow`, `_renameIdx`).
    **Zeichnen (`startGroupSelect`):** `_grpSel = {mode, stars:Set, rect, saved}`, Leiste
    `#grpsel-bar` + Gummiband `#grpsel-rect` (position:fixed). 3D: RECHTS-Drag = Box
    (Canvas-Handler prüfen `groupSelectActive()` VOR isRightDrag), Klick toggelt einen Stern
    (Zweig ganz oben in `handleViewerClick`), Box wählt nur was `starMaskPred` zeigt und
    nimmt nie etwas weg. **2D** (`mode='2d'`, aus `#plot-groups-btn`): Scatter = Box über
    `PLOT_STATE.star.screenPts`, Histogramm = BALKEN (`_toggleGrpSelBar`; `_grpRectEnd`
    schneidet nur in x gegen `histBars`; Balken merken sich ihre Sterne in `recs`, markierter
    Anteil in `col.pin`). Modus-Wechsel behält die Auswahl; Schließen des Plot-Fensters
    bricht ab. 3D-Handler prüfen `_grpSel.mode==='3d'`. Markierung im 3D = Suchmarker-Ringe
    (`setSearchMarkers`; `_searchMarkerStars` restauriert die vorherigen). ENTER/`✓` =
    `finishGroupSelect()`, ESC/`✕` = `cancelGroupSelect()` — beide mit
    `stopImmediatePropagation`, sonst schließt der globale ESC-Handler das Plot-Fenster.
  - **Sternfarbe = EIN Pfad für Dots und Vektoren:** `_starColorCtx(stars)` + `_starColorOf(s,C)`
    + `_syncStarColorWidget(C,vals)`; `buildStars` und `buildStarVectorArrows` rufen beide.
    Vektor-Modi färben nach dem gewählten Feld (keine erzwungene Magnitude). Abgeleitete
    Felder (`_deriveStarFields()` früh in `initScene`, nicht exportiert): `uvw_mag` und
    `pm_mag` — je eine Magnitude pro Vektor-Modus. Die Einzelkomponenten `U_pm/V_pm/W_pm`
    bleiben in den Daten, stehen aber bewusst in KEINEM Select (User-Wunsch). Pfeil-LÄNGE
    bleibt |v|. Die „Color by"-Zeile ist in ALLEN Modi sichtbar — inklusive „Uniform" +
    Farbpicker (Picker-Sichtbarkeit hängt allein am FELD, nie an `starVectorsOn()` — die
    Kopplung gab es in drei Pfaden und war ein Bug).
  - **`rv_used`:** boolescher Flag-Farbwert, Gruppe „Quality", 2D+3D-Farbe aber keine
    Plot-Achse (`STAR_AXIS_EXCLUDE`). Daten bleiben bool; nur `PLOT_SRC.star.val` coerced
    bool→0/1 (`+v`), damit `.toFixed` auf 2D-Achsen nie an einem Boolean scheitert.
- ∅-Button `#star-nodata-btn` (`toggleStarNoData`/`_syncStarNoDataBtn`): Sterne ohne Wert fürs
  Farbfeld grau zeigen oder ausblenden. Nur sichtbar, wenn nach einem Feld gefärbt wird.
- **Readout-Schema (`star-info`, Dots UND UVW-Pfeile, gleich in der 2D-Plot-Caption):**
  „**x of N** stars" (x = gezeichnete Dots, N = ALLE; ohne „of" wenn x=N), danach ` · `-Teile:
  `k greyed (no value)` / `k greyed (out of range)` / `k hidden (no value)` /
  `k hidden (out of range)` / `k masked out`. Ausgegraute zählen als GEZEICHNET.
- Custom-Farbwähler `#color-picker-pop` geteilt (star/plot/fplot/pline via `_pickerTarget`;
  Outside-Click-Ausnahme über Klasse `.color-swatch-btn`, nicht Id-Liste).
- Klick-Popup `#star-info-popup` (geteilt mit `showVoxelInfo`); `source_id` ist STRING (64-bit).
- Stern-Suche `searchStarById()` (mehrere IDs komma-getrennt): `_camFlight` + orange SDF-Ring
  (`setSearchMarkers`, Billboard-ShaderMaterial, geteilt `_searchRingGeo/_searchRingMat`).
  `showStarInfo` MUSS vor `setSearchMarkers` laufen (cleared den Ring).

### Plot-Fenster (ZWEI Instanzen: `#plot-window` Star + `#fplot-window` Field)
EINE parametrisierte Komponente, Key `w='star'|'field'`: State `PLOT_STATE[w]` (STATE-Block!),
Adapter `PLOT_SRC[w]`, DOM-Präfix `plot-`/`fplot-` (`_pid(w)`/`_pEl(w,suffix)`). Beide gleichzeitig
offen möglich, z-index 60. Canvas-gezeichnet, HiDPI (`renderPlot(w)`), Theme via `renderAllPlots()`.
- **Field-Fenster:** nur Maskenvoxel, Werte LIVE im aktiven Frame (`FPLOT_FIELDS`-Accessor-Map);
  Frame-Wechsel re-rendert offene Fenster (`rebuildForRefFrame()` → `renderAllPlots()`).
- **Color-by-Block** (nur Scatter): Regler + `hidden|greyed`, ∅-Button (`cNoData`), min/max-Zeile
  — Sichtbarkeit steuert `updatePlotColorControls(w)`; `onPlotColorFieldChange` resettet
  `cSel`+`cMin/cMax` beim Feldwechsel. Star-Fenster kennt zusätzlich x/y/z.
- **Export (PNG + einseitiges PDF):** `exportDataPlot` rendert auf ein Offscreen-Canvas mit
  `PLOT_EXPORT_SCALE` (**6**). Das Canvas wird in CSS-px gezeichnet und im PDF mit 100 px/inch
  platziert (`_canvasToPdfBlob`, dpi = 100·scale = 600 dpi), Seitengröße bleibt gleich. Das PDF
  ist handgeschrieben: ein JPEG (DCTDecode) auf einer Seite, kein Vektor.
- Modi **Histogram** / **Scatter 2D** / **Power spectrum** (nur Field): `_powerSpectrum(field)` =
  sphärisch gemitteltes 3D-FFT (`_fft1d/_fft3d`, zero-pad, in-Masken-Mittel abgezogen); `vmag` →
  totales E(k)=½Σ_c, **vx/vy/vz → E_c(k) der EINZELNEN Komponente** (à la Hutschenreuter+ 2026;
  Rückgabe-Feld `comp`, Summe = Total, y-Label `E_x(k)`), Skalare → |FFT|²; Power erzwingt
  log-log und versteckt X-Flip/X-Log/⟲.
  - **Log-Shells:** k-Schalen logarithmisch gespreizt (fundamental `1/Lmax` → Nyquist-Ecke,
    geom. Mittel je Bin); `nsh = clamp(round(2.5·log2(kmax/kmin)),8,40)`.
  - **Modell-Spektren (`meta.model_spectra`):** die INFERIERTEN Amplituden-Spektren des
    Forward-Modells — dünne Posterior-Sample-Linien + dickes Mittel je Komponente (exakt
    Hutschenreuter+ 2026 Fig. 4). Viewer: `_modelSpec()/_modelSpecFor(field)` (vmag = Summe
    der Komponenten sample-weise; `shared` = ein geteiltes Spektrum), Quellen-Button
    `#fplot-pssrc-btn`/`cyclePsSource()` (State `psSource` 'model'|'fft'|'both', Default
    'both', im `fieldPlot`-Blob; ohne meta versteckt + FFT-only). Skalare/curl haben kein
    Modell-Spektrum. Legende trägt den inferierten Power-Slope `s m±s`, Caption einen
    LS-Fit-Slope des FFT-Schätzers (`_psLsSlope`). Slope-Linien-Anker = Modell-Mittel.
  - **Sample-Zahl (`_psSampleNote`):** Mittel UND Slope liegen über ALLEN Samples des Runs
    (`meta.model_spectra.n_samples`). Die Zahl der gezeichneten Linien ist NICHT die
    Antwort — seit Aug 2026 sind es zwar alle, aber früher gebackene Dateien tragen
    weniger —, und da Runs auf unterschiedlich vielen finalen Samples enden, darf die
    Anzeige auch nicht konstant aussehen (der alte `Math.min(n_samples, rows.length)`
    meldete bei jedem Run „30 samples").
    Text: „40 posterior samples" bzw. „40 posterior samples (30 shown)"; steht in der
    Caption UND als Notiz-Zeile in der In-Plot-Legende, weil nur die Legende im PNG/PDF
    landet. Dafür nimmt `_drawPlotLegend` jetzt Zeilen mit `c:null` (Notiz ohne
    Farbstrich), und eine gezeichnete Modellkurve löst die Legende selbst aus: eine
    einzelne |v|-Kurve (kein Slope) bekommt eine Notiz-Zeile ohne redundantes Feld-Label.
    Export (`_model_spectra()`): Latent-Präfixe aus dem Posterior (x_/x_main_/main_-
    Konventionen beider Repos), CFM-Rebuild mit nshape = xi-Latent-Shape (drift-sicher),
    ≤64 log-k-Bins, ALLE Sample-Zeilen (der ≤30-Deckel ist im Aug 2026 gefallen — er
    sparte 15 KB von 12 MB; bei einem Run mit sehr vielen Samples wäre `rows` in
    `_model_spectra()` die Stelle für eine neue Schranke).
    **Normierung** (auf 3 Gittern verifiziert):
    E|FFT_k|² = amp(k)²/dV² → exportiert wird P_c(k)=½·amp²/dV², dieselbe y-Skala wie der
    FFT-Schätzer (der liegt wegen Maske+Padding systematisch darunter, Faktor ~3 bei
    test_no_sigma). **Slope-Konvention:** Latent standardisiert → physisch = prior_mean +
    prior_std·Latent, ×2 für Power; der LS-Fit weicht davon ab (flexibility-Wiggles +
    Sample-Mittelung) — beides zu zeigen ist Absicht.
  - **Overlays:** mehrere Spektren übereinander. State `PLOT_STATE.field.psOverlays=
    [{field,color}]`, Chip-Row `#fplot-spec-row` (nur power-Modus), Editor `#pspec-pop`
    (Fns `addPsOverlay/removePsOverlay/clearPsOverlays/setPsOverlay/renderPsChips/
    openPsEditor…`, Picker-Target `'pspec'`, Auto-Farben `_psAutoColor`). Cache `_psCache`
    ist eine **Map** `field → {sig,k,P,…}` (`_getPowerSpectrum(field)`), Invalidierung
    `_psCache={}`. Persistenz im `fieldPlot`-Blob; **Restore state-only** (renderPsChips
    liest FPLOT_FIELDS, bei `loadSettings` noch TDZ → Chips bauen erst beim Fenster-Öffnen).
- **CMD-Isochronen (Star-Fenster):** BHAC15-PMS-Isochronen (Baraffe+ 2015, Gaia-System, aus
  Chronos extrahiert) als eingebettete `const ISOCHRONES` (7 Alter 0.5–15 Myr). Nur im **CMD**:
  `_isCMD()` = star-scatter mit x∈{BP-RP,G-RP} und y=abs_g_mag; `_refreshIsoRow()` (Aufruf in
  `onPlotAxisFieldChange`+`setPlotType`) blendet `#plot-iso-row` ein/aus. State
  `PLOT_STATE.star.isochrones=[{age,color}]`, Chips + Editor `#iso-pop` (Fns `addIso/removeIso/
  clearIso/setIso/renderIsoChips/openIsoEditor…`, Picker-Target `'iso'`, `_isoXVal(pt)` wählt
  die x-Farbe). Gezeichnet im scatter-Zweig via `toScreen` → folgt flip/log/zoom, Legende im
  Plot, clip aufs Plotfeld. Persistenz im `plot2d`-Blob, **Restore state-only** (TDZ wie oben).
- **Achsen-Log:** je Achse `log`-Toggle (`togglePlotAxisLog`, State `logX/logY`); greift nur bei
  striktem Positivbereich (`_axLogOK`), Mapping `_axFrac`/`_axVal`; `stw.ax.axLogX/Y` = effektive
  Flags. Aktive Log-Achse wird im Achsenlabel als „(log)" gekennzeichnet.
- **Referenzlinien:** `PLOT_STATE[w].lines` = `{hist:[],scatter:[],power:[]}` PRO MODUS, Einträge
  `{axis:'x'|'y'|'s', val, color|null}` (null = auto `--accent3`); Zugriff IMMER über
  `_plotLines(w)`. **Power-Modus = STEIGUNGS-Linien** (`axis:'s'`, Default Kolmogorov −11/3):
  Gerade durch Anker `stw.ax.k0/P0` (erste k-Shell), Label `k^s`; `_restoreLines` hält power
  slope-only und hist/scatter x/y-only. Gezeichnet von `drawPlotRefLines(w,ctx,col)` (nutzt
  `stw.ax`; Hist-ax trägt `ymn/ymx` = Count-Achse). UI: „+ line" + Chips inline, „✕ all"
  (`renderPlotLinesUI`); Editor = floatendes `#pline-pop` (EIN Wertfeld + `#pline-axis-btn`-
  Toggle via `_plineToggleAxis`; bei Slope-Lines fixiert; `_plineApply(prop,val,live)`;
  Farbe über den geteilten Picker, Target 'pline'). Persistiert via `_restoreLines` (migriert
  Legacy-Einzel-Array). `setPlotType` schließt offenen Editor + swappt Chips. Linien landen
  in PNG/PDF-Exporten.
- **In-Plot-Legenden (Isochronen + Spektrum-Overlays):** EIN Helfer `_drawPlotLegend(ctx,col,
  rows,ax,sig,samples)` + `_pickLegendCorner(sig,bw,bh,samples)`; Cache `_legendCorner`. Die
  Ecke ist die LEERSTE, bestimmt aus den Datenpunkten in Fraktionen der VOLLEN Range — `sig`
  enthält Felder/Flip/Log/axOv/Zeilenzahl, aber NICHT `view` → Legende springt beim Zoomen
  nicht. Auto-Range-Rechnung des Scatter-Zweigs dafür herausgezogen als
  `_scatterFullRange(pts,stw)`.
- **Auto-Plotfarbe:** `_plotAutoColor(w)` = Preset-`pt` bzw. Theme-Accent je Modus (hist
  `--accent`, sonst `--accent2`) — Swatch, Picker UND Power-Kurve (`col.pt`) konsistent;
  `col.pin` (`--accent3`) nur für Fit-Kurven/Pins/Auto-Linienfarbe.
- **Scatter-Punkte OHNE Rand** (User-Wunsch; nur `arc`+`fill`).
- **Fit-Bereich (`#fitrange-pop`):** `PLOT_STATE[w].fitRange = [lo,hi]|null` schränkt NUR den
  Fit ein, das Histogramm bleibt vollständig (Unterschied zur Drag-Selektion `stw.range`).
  Button `#{p}-fitrange-btn` (Label = Grenzen), geteiltes Popup via `_fitRangeTarget`; Fns
  `toggleFitRangePop/closeFitRangePop/_setFitRange/_fitRangeCommit/_fitRangeClear/
  _fitRangeFromLines/_fitRangeFromAxis/_syncFitRangeBtn/_syncFitRangeInputs`. Leere Grenze =
  Achsenende. `_fitDistribution` bekommt Teilmenge + `fmn/fmx`; außerhalb wird abgedunkelt +
  gestrichelt markiert (landet im Export). Feldwechsel löscht die Grenzen, persistiert.
- **Histogramm-Fits** (`PLOT_STATE[w].fit`, max. einer): Gauss/Log-norm/Power law/Exp/KDE.
  `_fitDistribution` = MLE, liefert `curve` + `formula` (HTML-Mathe, `_fmName/_frac/_rad/
  _paren`) + `params`. Formel UNTER dem Canvas (`#…-fit-info`), Parameter oben rechts IM Plot
  (landen im Export). Exp = VERSCHOBENE Exponentialverteilung (x₀=min x); Lognorm/Powerlaw
  fitten x>0-Teilmenge. KDE pro Signatur gecached (`fitCache`).
- **Interaktion** in `_wirePlotWindow(w)`: Hover/Pin (nur Star; „copy IDs"-Button), Links-Drag =
  Range-Auswahl (Hist) / Pan (Scatter), Rechts-Drag = Range-Pan GESNAPPT auf Bin-Breiten (Hist) /
  x-only-Pan (Scatter), Wheel-Zoom, Dblclick/⟲ Reset (`resetPlotRange` nur aktueller Modus).
  Range/View/Pins Session-only. X-Feld pro Modus gemerkt (`xf={hist,scatter}`).
- **Style-Presets** `PLOT_STYLES` (STATE-Block, TDZ!). UI: „Style"-Button `#{p}-style-btn` in
  der Type-Zeile öffnet das geteilte `#style-pop` (Liste aus dem versteckten nativen
  `#{p}-style-select`); Fns `toggleStylePop/_stylePick/closeStylePop`, `_stylePopTarget` im
  STATE-Block. `setPlotStyle` synct das native Select (Restore-Pfad `_selSync`).
  **Colormap-Select** sitzt in `.p-cleft` (Sichtbarkeit via `updatePlotColorControls`).

### ENTER/ESC in den kleinen Popups
Tabelle `_POPUP_KEYS` (ganz unten im Script, nach allen close-Fns) verdrahtet `#fitrange-pop`,
`#axrange-pop`, `#pline-pop`, `#iso-pop`, `#pspec-pop`, `#group-pop`, `#color-picker-pop`:
ENTER übernimmt + schließt, ESC schließt ohne zu übernehmen. **Reihenfolge wichtig:** erst
`activeElement.blur()` (flusht ein `onchange`-Feld), dann `commit`, dann `close`.
Neues Popup = EIN Tabelleneintrag.

### Custom-Dropdown
`attachCustomDropdown(sel)` — verstecktes natives `<select>` + `.cdrop-btn`/`#cdrop-popup`
(position:fixed). `cdrop-sync`-Event nach programmatischen Value-Änderungen. Für Plot-Selects und
Sidebar-„Color by"; 3-Einträge-Selects bleiben nativ.

### Settings-Persistenz (`localStorage['vfv_settings_v2']`)
**Eigener Key seit Okt 2026** (`SETTINGS_KEY`): die eingefrorenen Runs/-Seiten teilen auf
GitHub Pages den Origin und behalten `vfv_settings` (`LEGACY_SETTINGS_KEY`) für sich — der neue
Viewer importiert ihn nur, solange der eigene Key fehlt, und schreibt ihn nie. Reset schreibt
`'{}'` (removeItem würde neu importieren). Payload = flache Keys (global + Datensatz 1, wie
bisher) + `datasets: {name → ds:true-Einträge}` + `activeDataset`.
**Tabellengetrieben:** `SETTINGS_TABLE` = `{key, get, set}`; neues Setting = EIN Eintrag.
`loadSettings()` läuft SYNCHRON beim Parse (vor initScene), danach `_postRestoreSync()`
UNCONDITIONAL. Star-Plot als Legacy-Einzelkeys + Blob **`plot2d`**, Field-Plot als EIN Blob
**`fieldPlot`** (beide inkl. `lines`).
- **⚠️ TDZ-Regel:** JEDE Variable, die save/loadSettings anfasst — auch was Setter nur LESEN
  (`_pid`/`_pEl`/`PLOT_STYLES`/`PLOT_STATE`/`CB_FILTERS`…) — MUSS im STATE-Block ganz oben
  deklariert sein, sonst bricht die Restore-Zuweisung still ab („halb restauriert").
  Setter dürfen NICHT `setPlotType`/`renderPlot`/`_restorePlotFields` rufen (PLOT_SRC in TDZ);
  nur State setzen + `_prefsPending=true`; Feld-Selects werden lazy angewandt
  (`populatePlotSelects` bevorzugt bei `_prefsPending` die Prefs).
- **Bei Feld-Umbenennungen immer Restore-Pfade prüfen** (persistierter unbekannter Name zeigt
  sonst nichts an).
- Reset-Button `resetSettings()` (Help-Sektion): leert Key + reload.
- **Settings-Datei (Help-Sektion „Save & load settings"):** `saveSettingsFile()` lädt
  `_settingsPayload()` (= exakt das, was `saveSettings` schreibt) als JSON herunter, gewrappt
  in `{_format:'vfv-settings', _version, result_name, repo, saved_at, settings}`.
  `loadSettingsFile(input)` validiert über `_settingsFromText(text)` (akzeptiert Wrapper UND
  blankes Objekt, verlangt ≥1 bekannten Key) → localStorage → `location.reload()`. **Bewusst
  kein Live-Apply:** der Reload benutzt den EINEN erprobten Restore-Pfad. Fremde Keys ignoriert
  der Table-Pass → Dateien zwischen Runs austauschbar. Fehler in `#settings-file-note`.
  ⚠️ Features leben im TEMPLATE — gebackene `*_data.html`/`Runs/*.html` bekommen sie erst
  durch einen NEUEN Export.

### Fresh-Load-Defaults
Streamlines AUS; wenn an: animated / animSpeed 0.10 / count 200 (Slider 5–1000,
`MAX_PARTICLES=1000`). Field subsample 1. refFrameMode='raw'. viewerStyle='midnight'. Defaults
stehen KONSISTENT in `params`/`vis` (JS), HTML-`value=`/`class="on"`, Section-display — bei
Änderungen ALLE anpassen.

### Sonstige Feature-Anker (Funktionsnamen zum Greppen)
**Screenshot-/Video-Colorbars** (`compositeColorbarsOnto`, `drawColorbarPanel`/
`drawColorbarVertical`, `colorbarPanelDims`): NUR im Export, im Live-3D keine Overlays.
Exportauflösung frei (`applyExportSize`) → ALLE Geometrie-/Font-Konstanten Referenzpixel ×
`dims.s` (`_cbScale(ch)` = ch/1000, geklemmt 0.8…3, × `_CB_BUMP` 1.35). `colorbarPanelDims`
klemmt `s` zusätzlich so, dass der Bar-Stapel in die Canvas-Höhe passt, und liefert `s` mit.
Labels durch `_cbFitLabel()`: iterativ schrumpfen (3 Pässe), dann „…" statt clippen.
Energie in J/pc³ (`EKIN_TO_J`/`EDENS_TO_J_PC3`), `kineticEnergyIntegral()` (+`_ekinCache`),
`showVoxelInfo`, `drawColorbarKde`, Kamera-Bookmarks (`camBookmarks`/`_camFlight`),
Video/Screenshot-Modal (Bookmark-Tour `_tourOrder`/`_reconcileTourOrder`), einklappbare
Sektionen (`collapsedSections`), Slider-Doppelklick (`wireSliderTyping`), Objekt-Label-Größe
(`objParams.labelScale`, 1×–5×; `applyLabelScale()` skaliert `userData.labelBase` in place
über G.objects/G.dust/G.lbubble).
`makeTextSprite` passt die Canvas-Breite an die Textlänge an (Zweierpotenz gegen
WebGL1-NPOT-Blackout, Höhe fix 128), `userData.textAspect`; `addObjectLabel` setzt die
Quad-Breite = baseH·textAspect (lange Namen verbreitern statt clippen).
**Live-Video (Camera path „Live", Okt 2026):** `startLiveRecording()` nimmt auf, was
`animate()` rendert (Auto-Rotation, Slice-Sweep, Kamera, Slider …) bis `stopLiveRecording()`
(roter `#rec-bar` oben mit Timer + ■ Stop; ⬇ bzw. Taste S → `openScreenshotModal()` stoppt
eine laufende Aufnahme). Pro Frame (`_liveRecFrame`, Hook in `animate()` NACH dem Render)
wird das WebGL-Canvas in ein Frame-Canvas FESTER Größe (Viewgröße beim Start) kopiert —
Größenänderung mitten in der Aufnahme wird gelettert, die Videogröße bleibt; Colorbars per
`compositeColorbarsOnto`. Keine Sidebar-/Auflösungsänderung (Live-Pfad versteckt Duration +
Resolution). **`_liveRec` im STATE-Block** (animate-TDZ). Headless: MediaRecorder liefert
unter virtueller Zeit KEINE Daten (auch der 360°-Pfad nicht) → Inhalt nur im echten Browser
prüfbar; die Tests prüfen Start/Stop/UI/Letterbox.
**Info-Modal (Taste I):** eigenes Overlay `#info-overlay`/`#info-modal` neben dem Help — teilt
CSS, aber EIGENE IDs (doppelte IDs brachen den `querySelector`-Test). Inhalt aus
`meta.run_info`: „Loaded Result", letzter minisanity-Block, Parameter-Dump (`_fillRunInfo()` in
`initScene`). Exportseitig: `_minisanity_tail()`, `_parameters_dump()` (claude:
`parameters_used.txt`; taurus: pprint aus `Parameters/<run>.py` mit Drift-Vermerk).
Tasten: **I** Info, **S** Screenshot, dazu H/?/M/R — im Help unter „Navigation → Keys".
**Help-Menü** (`help-section`s im HTML ~Zeile 1525) bei neuen Features MITPFLEGEN (User-Wunsch).
Reihenfolge: ZUERST die Einstellungen (Navigation … Screenshot), DANACH Fließtext (Loaded
Result, About, Reference Objects, Reset). Einträge kurz.

## Export-Pipeline
`export_vectorfield.py`: `DATASETS`-Liste, `process_dataset()` rechnet selbst (ohne `run` nur den
Sternkatalog; fehlende optionale CSV-Spalten → leer, Pflicht nur source_id + X/Y/Z):
NIFTy-Samples, Curl/Div, Residuen, KDE-Maske, Modell-Spektren). Schalter oben: `SAVE_JSON`,
`SAVE_HTML_LIGHT`, `LIGHT_LB_LEVELS`.
- **Batch-Light-Export:** `python export_vectorfield.py batch` (beliebiges Python — der
  Treiber subprocesst je Run das richtige Venv) exportiert für jeden Eintrag in `BATCH_RUNS`
  (Dict oben im Skript, Key "T"/"C") NUR die Light-Version nach `Viewer/Runs/<run>_light.html`
  (Flag `--light-to-runs`, Hauptdateien bleiben unberührt, kein JSON). index.html-Einträge
  bleiben Handarbeit. Gebackene Runs/-Dateien bekommen neue Template-Features nur durch
  Re-Export.
- **Light-Version** `vectorfield_viewer_light.html`: ohne Dustmap UND nur mit den
  `LIGHT_LB_LEVELS` (=2) gröbsten Local-Bubble-Stufen (NSIDE 8/16) → ~2.2 MB.
  Viewer-seitig nichts nötig: `refreshLocalBubbleSlider()` leitet Slider-Max aus
  `lbubbleNsides()` ab und klemmt einen gespeicherten Index fest.
- **Datenformat 2 (Okt 2026):** `{format:2, datasets:[{name, meta, stars, voxels?}],
  reference_objects}`. `stars` = ein Array pro Größe (leere Spalten entfallen; vorher standen
  die ~37 Schlüssel in jedem Stern = 222 von 373 KB), `voxels` = je Spalte `_q16`: uint16 +
  base64 mit `lo`/`step` (65535 = kein Wert; Stufe ≤ 4e-4 km/s, feiner als die alte Rundung
  1e-3; 1.06 → 0.42 MB). Viewer: `_normalizeData()` dekodiert in die gewohnten Strukturen
  (`real_stars`-Objekte, `voxel_columns`), alles dahinter unverändert; altes flaches Format
  (meta/voxels|voxel_columns/real_stars) läuft durch. Ohne Massen: `meta.mask_kind="stars"`,
  `mask_level` in Sterne/pc³ (Default 4.4 % des Peaks). Außerdem entfernt der Export ganze
  `//`-Kommentarzeilen aus dem Haupt-`<script>` (`_strip_comment_lines`, −160 KB; sicher: in
  Template-Literalen stehen nur GLSL-Kommentare) — make_test.py backt mit derselben Funktion.
  Taurus light: 2.18 → 1.17 MB.
- **Voxel-Spalten (`voxel_columns`, intern nach dem Dekodieren):** ein Array pro Größe
  (`vx/vy/vz`, `std_x/y/z`), C-Order über (ix,iy,iz), Index `(ix*ny+iy)*nz+iz`. NICHT mehr
  übertragen, weil im Viewer exakt reproduzierbar: `x/y/z` + `ix/iy/iz` (aus
  `meta.extent`/`meta.spacing`) und `curl_x/y/z` + `div` (np.gradient-Äquivalent aus vx/vy/vz).
  `_hydrateVoxels()` (vor `initScene`) baut daraus die Voxel-OBJEKTE — alles dahinter arbeitet
  mit `DATA.voxels`; alte Exporte und Drag&Drop-JSON mit `voxels` laufen durch (Early return).
  `_grad3()` muss die np.gradient-Randformeln treffen (zentral innen, einseitig am Rand),
  sonst driften curl/div von `meta.curl_min/max` weg; abgesichert durch `HYDRA_REF` in
  make_test.py und einmal gegen echtes numpy geprüft (Abweichung 0).
- **Dichten werden NICHT exportiert:** `_hydrateVoxels()` ruft `_seedKdeDensities()` und
  rechnet `mass_density` + `density` beim Laden aus `meta.kde` + Sternpositionen/-massen
  (je ~10 ms). Trifft die früher exportierten Werte auf 7e-7 bei Peak 0.087, Maske bei
  Default-Level unverändert 1817 Voxel. `maskKdeFactor` wird in `_hydrateVoxels()` aus
  `meta.kde.smooth` geseedet, außer ein gespeicherter Wert war da (`_kdeFactorRestored`).
- **⚠️ `meta.kde.spacing` (Bugfix Juli 2026):** BEIDE Repos werten die KDE auf den Feldknoten
  aus (origin + k·distances). Vorher benutzte `TaurusVelocityField/simple_functions.py` ein
  `np.mgrid` mit inklusiven Enden (Schritt shape/(shape-1)·distance) — betroffen waren Maske,
  massengewichtetes v_ref und die Energieintegrale (final_run: 1611 → 1823 Maskenvoxel). Der
  Viewer hatte die alte Formel fest verdrahtet und rechnete bei Claude-Exporten auf einem um
  5 % gedehnten Gitter. Jetzt schreibt `_kde_eval_spacing()` die Schrittweite mit und
  `computeKdeDensity` liest sie; die alte Formel bleibt Fallback für gebackene Dateien ohne
  den Key — für die ist sie richtig.
- **Density-Cloud** hat drei Felder: `density` (= MASSENdichte; Key heißt aus
  Settings-Kompatibilität so), `stellar_density` (stars/pc³), `energy_density`.
  `_derivedRange()` führt beide Dichten getrennt.
- **Rundung im Export:** `vx/vy/vz`/`std_*` 3 Nachkommastellen (Effekt auf curl/div ~5e-4),
  Dichte-relevante Spalten über `_col_sig()` auf 5 SIGNIFIKANTE Stellen mit `floor=1e-9`
  (feste Nachkommastellen kippten Voxel am unteren Slider-Ende in/aus der Maske).
- Meta: `v_ref`, `sun_motion_lsr`, `voxel_volume`, curl/div/std/density-min/max.
  Frame-abhängiges wird NICHT exportiert (live im Viewer).
- Sterne: `rv` inkl. Outlier, U/V/W, `rv_used`, `name_luhman`/`name_sigma` ('-' → None via
  `_cat()`; Spalten optional), `source_id` (STRING), ruwe, age/mass/extinction, `mass_err`,
  Photometrie, pm/rv + errors + residuals. `rv_good` existiert nicht mehr.
- **Noise-Estimation eta:** `_eta_from_posterior()` rekonstruiert den InvGamma-rv-Noise-Faktor
  pro Stern aus den Posterior-Latents (`noise_estimate_*_w_rv[_sampled]`). Sternmenge aus
  **Gaia.csv** (nicht dem Stern-CSV!), gegen die Latent-Längen VERIFIZIERT; Strategien in
  Prioritätsreihenfolge: (1) heutiger stellar_data.py-Stand, (2) Legacy NUR für Runs der
  final_run-Ära (ruwe 1.4 hardcoded + damalige fehlerhafte rv_integral-Formel mit rv_err statt
  rv — seit sigma_int05 gefixt; die Verifikation entscheidet automatisch). Kein Match →
  eta=None + Warnung (Viewer blendet die Felder aus). **`rv_used` kommt IMMER aus den
  Filterkategorien** (korrektes rv-Integral + filter_ruwe + filter_rv_error; User-Entscheid),
  NICHT aus der eta-Menge — die bleibt an die tatsächliche Inferenz-Sternmenge gebunden
  (None außerhalb, zeilengleich zum Stern-CSV). Bei final_run weichen die Mengen ab
  (rv_integral-Bug: 114 rv_used vs. 112 eta); wird beim Export als Hinweis geloggt. Dieselbe
  Kandidaten-Strategie steckt in plot_data.py Sektion 3b (fällt bei Shape-Mismatch auf die
  Legacy-Maske zurück; eta dort immer CSV-langes NaN-Array). Exportfelder: `eta`, `eta std`,
  `log10 eta`, `pm{ra,dec}/rv residual weighted` (Residuum/Katalogfehler, OHNE sigma_int),
  `rv residual eta weighted` (= /σ·√η). Viewer: Gruppe „Noise estimate" + erweiterte
  „Residuals" in `STAR_FIELD_GROUPS`; `eta`/`eta std` in `STAR_3D_COLOR_EXCLUDE`
  (heavy-tailed — 3D färbt man mit `log10 eta`); Info-Karte zeigt η ± std
  (`STAR_INFO_ERRPAIR`).
- **Dustmap q8:** `reference_objects.dustmap = {grid:{origin,spacing,shape},
  q8:<base64 Uint8 180³>, val_cut, val_max, spacing, color, name}`, 0 = unter Cutoff
  (60. Perzentil), 1..255 log-quantisiert bis val_max (99.5. Perzentil). Das dichte Gitter
  ist direkt die 3D-Textur des Raymarchers (s. Viewer-Sektion „Dustmap"); `_decodeDustQ8`
  cached. Legacy xyz/val wird beim Laden voxelisiert.
- **Local Bubble q16:** `{bbox, levels_q16:{"8"…"128":<base64 interleaved Uint16 xyz>}}`;
  `_decodeLbubbleLevel` dequantisiert + cached (`lb._q16`). Fallback legacy `levels`.

## Datenquellen (Literatur)
Taurus+Regionen: Zhou, Li & Chen 2025 (arXiv:2509.18496) Tab. 2 · Per-Tau Shell (Zentrum+Radius):
Bialy 2021 Tab. 1 · Orion-Eridanus: grobe Ellipsoid-Näherung (Joubaud 2020, Pon 2014/16) ·
Local Bubble: Pelgrims 2020 (L19_map-inner_final.fits) · Musca/CrA/Pipe: Zucker 2020/21 ·
Dustmap: Edenhofer 2024 · Sonnenbewegung LSR (11.1, 12.2, 7.3): Schönrich 2010.

## Bekannte Bugs & Lösungen (dauerhaft relevant)
- **HUD-Overlay `pointer-events:none`:** jedes interaktive Element in `#viewer-hud` braucht
  `pointer-events:auto`, sonst geht der Klick aufs Canvas (Outside-Handler schließt sofort).
- **Video ohne Rotation (Firefox):** IMMER `captureStream(fps)` mit echtem Wert, in BEIDEN Pfaden
  (Composite-Pfad ruft `compositeColorbarsOnto()` pro Frame). Zeitbasiert (performance.now()).
- **Glow unsichtbar im Light Mode:** AdditiveBlending sättigt gegen Weiß → `glowBlending()` =
  Additive (dark) / Normal (light), gesteuert vom `dark`-Flag des 3D-Styles; `setViewerStyle`
  swappt Material-Blending in place (beim Dust-Volume zusätzlich die `uAdditive`-Uniform).
- **GLSL3-ShaderMaterial (r128) hat KEIN `gl_FragColor`:** der GLSL3-Prefix von three r128
  definiert nur texture2D→texture u. ä., aber keinen FragColor-Alias — eigenes
  `out vec4 fragColor;` deklarieren. Fehlerbild: „'gl_FragColor' : undeclared identifier",
  und der Layer bleibt einfach leer (Compile-Fehler nur in der Konsole).
- **Achsen-Labels vs. Punktwolken:** `depthWrite:true` für Shells + renderOrder; Text-Sprites
  brauchen `depthWrite:false` im SpriteMaterial (sonst verdeckt das transparente Quad).
- **Kamera-Persistenz:** initScene überschrieb restaurierte Kamera → `_camRestored`-Flag,
  Default-Framing nur ohne Save.
- **`dispose()` ohne `remove()` = Geister-Mesh:** eine disposte, aber noch in der Gruppe
  hängende InstancedMesh RENDERT WEITER — three.js lädt sie aus den noch vorhandenen
  Attribut-Daten neu hoch. In JEDEM Rebuild-Pfad erst `G.<gruppe>.remove(mesh)`, dann
  `geometry/material.dispose()`. Regressionstest: Mesh-Zahl über mehrere Toggles zählen.
- **Label-Duplikate:** `addObjectLabel(…, group)` — Labels in die Gruppe des Builders legen,
  der sie auch aufräumt (Local Bubble/Dust hatten Geister-Labels in G.objects).
- **Datei-Falle String-Edit:** Steuerzeichen (`\x01`) im Code ließ String-Edits scheitern →
  per Python-Zeilenbereich ersetzen.
- **TDZ bei Settings-Restore:** s. Settings-Sektion — häufigste Fehlerquelle bei neuen Keys.
- **Permission-Regeln:** absolute Pfade in settings.json-Regeln brauchen `//`-Präfix
  (ein `/` = relativ zur settings-Datei) — sonst greift die Regel still nicht.

## Versionierung / Backups
Kein Snapshot-System; Änderungen werden bestmöglich mit git dokumentiert.
Vor großen Änderungen ggf. selbst eine Kopie ziehen.

---

## Mehrere Datensätze (Regionen) + Nur-Sterne-Modus (Okt 2026)
**Prinzip: Funktionen einmal, Zustand pro Datensatz.** `DS[i] = {name, data, hasField, st, G,
root}` (STATE-Block). Die Globals (DATA, Settings, Caches, Meshes, `G.arrows/streams/stars/
cloud/box/axes`) halten IMMER den Zustand von `DS[dsCur]`; `withDataset(i, fn)` tauscht Satz i
ein, führt fn aus, tauscht zurück. `dsActive` = der Satz, den die Sidebar bearbeitet
(außerhalb von withDataset gilt dsCur === dsActive). Sektion „DATA SETS" im Template.
- **Tauschlisten:** `DS_SET` (Settings-lets, neu gebunden), `DS_INPLACE` (Setting-OBJEKTE, in
  place kopiert, weil Closures sie halten — `wireCbFilter` hält `cbFilter[layer]`; die
  gelisteten Unter-Keys `params.autoRotSpeed`, `vis.objects` bleiben global), `DS_RUNTIME`
  (Caches/Meshes, `_dsFreshRuntime()`), `DS_GROUPS` (eigene Gruppen je Satz unter `root`,
  gleiche renderOrder). Zugriff über `Function()`-Accessoren (top-level lets sind global).
  **Neue per-Satz-Variable = Name in die passende Liste**, sonst teilen alle Sätze sie.
  `_starCatCache` wird beim Tausch geleert. Global: Objects, Kamera/Bookmarks, 3D-Style,
  Plot-Fenster (zeigen den aktiven Satz), eigene Sterngruppen (per source_id auf alle Sätze).
- **`forEachDataset(fn)`** = alle Sätze, der AKTIVE zuletzt; `buildAll()` → globale Builder
  einmal + `buildDatasetLayers()` je Satz. Sidebar-Schreiber in Buildern
  (`updateColorbar/updateStreamColorbar/updateCloudColorbar`, `_syncStarColorWidget`,
  `star-info`) sind mit **`_uiCtx()`** gesperrt, solange ein nicht-aktiver Satz eingetauscht
  ist. Globale Pfade, die Satz-Layer anfassen (setViewerStyle, Custom-Style-Farben,
  customGroupsChanged, animate→tickParticles), laufen über forEachDataset.
- **Wechsel `setActiveDataset(i)`:** `_flushDeferred()` (offene rAF-/debounce-Rebuilds gehören
  dem ALTEN Satz — `debounce` merkt sich dafür fn, `flushDebounces()`), Swap, `_syncDatasetUI()`
  (= Sidebar komplett aus dem Zustand: `_syncDsWidgets` + `_postRestoreSync` + Dropdowns +
  Maske + `_syncFieldAvailability`), Plot-Sessionzustand/Pins zurück.
- **Settings pro Satz:** SETTINGS_TABLE-Einträge mit `ds:true`; gespeichert unter dem NAMEN
  (`_dsSavedBlobs`, auch für Sätze, die nicht in der Datei sind). Satz 1 startet aus den
  flachen (restaurierten) Keys, weitere aus `_DS_DEFAULTS` (Snapshot direkt VOR
  `loadSettings()`) mit eigener Sternfarbe (`DS_STAR_COLORS`); `_applyDsBlob()` wendet einen
  gespeicherten Satz mit DATA=null an (wie der Parse-Time-Restore — Setter bauen nichts).
- **Globales unsichtbares Gitter:** `sceneExtent()` = Vereinigung aller Sätze → Start-Kamera +
  Größe der Referenzobjekte. Jeder Feld-Satz behält eigenes Gitter, Grid-Box und Achsen.
  Kamera-Presets rahmen den aktiven Satz; „⌖ Fly to" (`flyToDataset`) fliegt hin, Blick entlang
  der (1,1,1)-Diagonale. Wechseln bewegt die Kamera nicht.
- **Picking:** `_pickDataset()` = Satz mit dem nächsten Treffer (Pfeil/Stern) entlang des Rays,
  Hover (`_hoverAt`) und Klick (`_clickPick`) laufen in dessen Kontext; Sternsuche über alle
  Sätze (aktiver zuerst). Info-Karten tragen den Satznamen (`_dsSuffix`).
- **Nur Sterne (`run=None`, `hasField()` false):** `DATA.voxels = []`, `meta.extent` aus den
  Sternen, `meta.spacing` = Gitterabstand der Feld-Sätze (sonst 1/40 der Ausdehnung) für
  Sterngrößen. Alle Feld-Builder inkl. Achsen/Box brechen ab; `_syncFieldAvailability()`
  versteckt Feld-Toggles, Reference Frame, Mask, Field-Plot und „RV used"; Sterne beim Laden
  an. Settings werden nur ausgeblendet, nie verändert.
- **Ohne Massen (`_noMass()`, meta.mask_kind "stars"):** Maske/KDE nur über die Sterndichte
  (`recomputeMaskDensity` ohne md), „By mass" + Cloud-Felder ρ/½ρv² ausgeblendet,
  cloudField → stellar_density.
- Wechsler `#section-datasets` (nur bei ≥2 Sätzen), Help-Eintrag „Data sets". HUD-Tag:
  `_syncRunTag()` („Taurus · [C] test_no_sigma" bei mehreren Sätzen).
- **Tests:** `tests/make_test.py` baut zusätzlich `test_multi.html` (Alpha Feld+Massen, Beta Feld
  ohne Massen woanders, Gamma nur Sterne, Format 2); `run_tests.sh` fährt beide (Multi mit
  `--virtual-time-budget`, prüft auch das Auto-Init-Re-Init). Feldpfeile und Sternvektoren
  teilen `_vectorGlyphMeshes()` (Cone+Shaft-Helper).
