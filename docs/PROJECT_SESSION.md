# AI Digital Twin Generator: the full session log

Everything done on this project in one working session, 8 and 9 October 2026, from the first read of
the repository to the last push. Written from the git history, the session transcript and the
measurements taken along the way. Where something was **not verified**, it says so.

- Upstream project: <https://github.com/komaldewangan-24/Twin-Generator> (an MCA project by Abhinav's friend)
- Working copy: `~/Projects/Twin-Generator`, branch `improvements`, pushed to `origin main`
- Machine used for every test: Apple M4, 16 GB, macOS, Python 3.13 (via `uv`), Node 26
- Never tested: Windows, the friend's HP Victus with an RTX 3050 (4 GB), a real phone recording, live
  Gemini / Claude / Ollama calls

## Contents

1. [The goal](#1-the-goal)
2. [At a glance](#2-at-a-glance)
3. [Timeline: every request and what came of it](#3-timeline-every-request-and-what-came-of-it)
4. [How the app works now](#4-how-the-app-works-now)
5. [Every bug found and fixed](#5-every-bug-found-and-fixed)
6. [Every feature added](#6-every-feature-added)
7. [Security and privacy](#7-security-and-privacy)
8. [Small and Windows GPUs](#8-small-and-windows-gpus)
9. [The quality investigation (numbers)](#9-the-quality-investigation-numbers)
10. [Detection: what works and what does not](#10-detection-what-works-and-what-does-not)
11. [Tests](#11-tests)
12. [Scripts and settings](#12-scripts-and-settings)
13. [All 20 commits](#13-all-20-commits)
14. [Mistakes I made and corrections](#14-mistakes-i-made-and-corrections)
15. [Limits and what was not verified](#15-limits-and-what-was-not-verified)
16. [What the friend needs to do](#16-what-the-friend-needs-to-do)
17. [Ideas not done](#17-ideas-not-done)
18. [Appendix: every message you sent](#18-appendix-every-message-you-sent)

---

## 1. The goal

The problem statement the project must follow, in your words:

> AI Digital Twin Generator is a platform that transforms a simple smartphone video into an interactive
> 3D digital representation of an indoor space. The generated digital twin enables visualization, object
> analysis, floor plan generation, and natural language interaction with the environment.

Your friend's version could upload a video and detect objects in 2D, but it had no real 3D step, so the
"digital twin" was not automated. The work below closes that gap and fixes what was broken.

You also set a working style that I followed throughout: **implement, verify and show**, not only advise
("you are telling the things").

## 2. At a glance

| | Start (`52f283d`) | Now (`189be67`) |
|---|---|---|
| 3D model | attach a splat trained elsewhere, by hand | built automatically from the video (COLMAP camera path + Brush training) |
| Object positions | camera-view coordinates, duplicates counted twice | placed on the floor in 3D, merged across frames |
| Floor plan | blob outline, tiny icons | straight walls, real-size furniture, interactive, doors/windows when found |
| Room size | only from a number you typed | estimated from the reconstruction, correctable by measuring in 3D |
| Files | public by URL | signed, short-lived, owner-only links |
| Backend tests | 12 | 82 |
| Repo changes | | 113 files, +8,383 / -1,477 lines, 19 commits on top of the initial one |

Headline results:

- **A real photoreal 3D model from video**, tested on a public sample: 207 of 210 frames placed in 3D, room
  4.7 x 3.7 m, ceiling about 2.3 m.
- **Sharper model**: the browser view of the same scan went from 22.6 dB to 26.0 dB just by fixing the
  converter, then to 27.4 dB with the new default training (PSNR against photos the model never saw).
- **Works without a GPU for the "3D" part**: a Structure view (the colored point cloud, room box and
  camera path recovered from the video) shows even when the photoreal model cannot be trained.
- **Demo scan bundled in the repo** so anyone can see the full app with no GPU, trainer or video.

## 3. Timeline: every request and what came of it

### Day 1, 8 October

**1. "Have a look at this project my friend is making for MCA, tell me all the not-working things and how I
can fix it."**
I read the whole repo (backend, frontend, tests, README, PLAN) and reported what was wrong, in order of
severity: backend would not start on a fresh install (missing `email-validator`); Objects, Analytics,
Floor plan and Chat tabs and the PDF crashed after processing (the API returns `{detections, meta}` but
the page treated it as a list); wrong password showed no error; short videos failed; "Re-upload" did
nothing after a failure; empty JWT secret allowed forged tokens. Then the bigger design problems
(detections merged by screen position, so one chair seen twice counted twice), a chat that answered the
wrong question, security holes (every user's video public by URL), and stale docs.

**2. "First run it locally so I can check it."**
Got it running: system Python was 3.9 and the backend needs 3.11+, so I built a 3.13 venv with `uv`.
`pip install -r requirements.txt` failed on macOS (`ultralytics` needs `numpy<2`, the file pins
`numpy==2.1.3`), so I removed `ultralytics` from the requirements and exported the detector model in a
throwaway venv. Confirmed the bugs by actually running them (wrong password, Objects tab crash,
5-second video failing, unauthenticated media download). Your friend's 12 tests all passed, which is why
nothing looked broken to them.

**3. A screenshot of a failed scan plus the PRD: "check all things, tell me how to improve, make the UI
better, and check if something like this exists."**
Your screenshot showed the short-video `vconcat` crash. I split the work into three:

- *Gap analysis against the PRD* (a table of what was built, partial or missing).
- *Prior-art research* by a background agent: no single product or repo did the whole combination
  (video to splat, object counts, floor plan, chat, dashboard) free on a Mac. Polycam, Scaniverse, Luma,
  KIRI Engine and Matterport cover capture and splats; RoomPlan, magicplan and Canvas need LiDAR; Yembo
  already does AI object inventory from phone video, so "first object inventory from video" is not a
  claim to make. Closest open source: `splat-local`. Defensible angles for a viva: a free local no-LiDAR
  stack, chat grounded in structured scan data, restaurant-specific metrics, and an honest accuracy study.
- *A new UI*, using the frontend-design skill: a surveyor's drafting-table identity (fog-grey paper,
  ink-blue lines, one fluorescent orange, Bricolage Grotesque headings, IBM Plex Mono figures, installed
  locally so nothing loads from a CDN).

I also fixed the bugs that blocked checking the UI (the crashes above, short videos, re-upload, JWT, delete
leaving files, stuck "processing" after restart, upload races, error leaks, case-sensitive emails,
seating capacity and chat answers), with tests, and confirmed the new short-video test fails on the old code.

**4. "Copy it and the 3D model generation is not good and realistic, make it something realistic and start
improving."**
Copied the project to `~/Projects/Twin-Generator` (working directory changed). You approved downloading a
public sample (about 650 MB; the "playroom" scene of the Deep Blending dataset, 225 photos, made into a
video). Built the real pipeline:

1. FFmpeg extracts frames.
2. **COLMAP** (via `pycolmap`) recovers camera poses and a sparse point cloud.
3. YOLOv8s detects objects; each sighting is placed on the floor in 3D and merged across frames.
4. Room size, floor area, ceiling height and free space are estimated from the reconstruction.
5. **Brush** (Apache-2.0, runs on Metal/Vulkan/DX12, no NVIDIA needed) trains a Gaussian splat.
6. The 100-200 MB training file is converted to a compact `.splat` (183 MB down to about 13 MB at the time).

Result on the playroom: 207 of 210 frames registered, about 16 minutes of training, a genuinely
photoreal model. Also done in this step: files made private (signed links), chat upgraded, accuracy
script written (see sections 5 to 7).

**5. Your problem statement again: "have to follow this."**
I audited the app promise by promise and fixed the gaps: portrait phone video was shrinking to 405 px wide
(now keeps 720); upload limit raised to the PRD's 2 GB; **Walkthrough** (replays the filmed path);
floating **labels** on objects; **Show in 3D** from the Objects tab, floor plan and assistant; assistant
that can use any language model. I caught my own privacy bug here: my first LLM code auto-picked an
`ANTHROPIC_API_KEY` from your shell and would have sent scan data to an AI service you never chose. It now
ignores shell keys; only `LLM_PROVIDER` + `LLM_API_KEY` in `.env` select a provider, and a test pins that.

**6. "Commit all the changes in 6 commits and tell me what my friend needs to do."**
Six commits on `improvements`, each checked in a scratch checkout (tests at commits 1 to 3, builds at 4 to
6). Then a checklist for the friend (install, detector model, Brush, `.env`, real-video test, accuracy
measurement, limits to explain).

**7. "Push them to main directly" / "I'm now the contributor, so push it."**
My pushes were blocked twice by the permission check, which I respected rather than working around. You
ran the push yourself: `52f283d..16002ad  improvements -> main`.

### Day 2, 9 October

**8. "My friend ran it on the Victus laptop (RTX 3050). He couldn't see the 3D model. Have a look, and I want
a good enough 3D model to show in the project."**
I could not reproduce his exact failure (no Windows, no 3050), so I fixed every likely cause. Details in
section 8. The most important: the demo scan, the one-command setup scripts, and a `doctor.py` that
explains why 3D is not working. I tested a fresh clone as the friend would get it. Pushed
(`16002ad..3881300`).

**9. "In Victus I am getting some error while downloading Brush."**
I never saw the original error, so I hardened the installer against every usual cause (dropped
connection, certificate problems, antivirus, damaged archive, missing Visual C++ runtime) and added a
manual route. I verified against the real Windows zip layout. Pushed (`..b437c97`).

**10. "According to my problem statement a 3D structure is generated from the video. Can you check if yes,
and generate a demo so I can see it?"**
Yes: structure-from-motion triangulates thousands of real 3D points, which the app used to throw away.
I now export them and show them in a **Structure** view. I re-ran the whole pipeline live as a new scan:
207 frames registered, about 17,000 points with 0.84 px mean error, room 4.7 x 3.7 m. Pushed.

**11. "Working great. We can make the floor plan modern and great."**
Rebuilt the floor plan (section 6). One bug caught while testing: my first zoom version swallowed every
scroll, so you could not scroll the page past the plan. Zoom now needs Ctrl/Cmd, which is also what a
trackpad pinch sends.

**12. "Now tell me what all things I can add."**
A list of about 25 ideas grouped by effort. You picked the top three.

**13. "Plan and do 1, 2, 3."**
(1) a **Measure** tool with a persistent scale, (2) **Record** the walkthrough as a video, (3) **doors,
windows and lights**. Built, verified in the browser, committed.

**14. Two screenshots of the viewer: "I think we can improve the quality."**
A measured investigation, not a guess (section 9). Found that the converter threw away half the model,
fixed it, tuned the training, retrained the demo, and wrote it all down.

**15. "Push them to main."** `655b5f8..189be67`, which also carried the floor-plan redesign that had not
been pushed before.

**16. "Generate a whole session md file."** This document.

## 4. How the app works now

### Pipeline (one upload)

```
video --> EXTRACTING   ffmpeg, 4 fps, scaled by the SHORT side to 720 px (portrait keeps 720x1280)
      --> POSES        pycolmap: pick up to 240 sharp frames, exhaustive matching, incremental mapping
                       fails clearly if fewer than 12 (or 35%) of the frames register
      --> DETECTING    YOLOv8s (ONNX) + optional YOLO-World (ONNX); each box placed in 3D and merged
      --> TRAINING_3D  Brush, sh-degree 0, growth schedule, retry once with lighter settings if it crashes
      --> DONE         convert .ply to compact .splat, drop the training file
```

Objects, floor plan and analytics are available as soon as the camera path is solved, while the 3D model
trains. If poses cannot be recovered the scan still completes in 2D mode and says why. A missing detector
or failed training never loses the scan.

### Spatial grounding (`spatial.py`)

- **Up direction**: mean camera "up", snapped to a RANSAC plane when it is within 25 degrees.
- **Floor and ceiling** from percentiles of the sparse points. **Scale**: the phone is assumed held at
  1.4 m and the ceiling at 2.5 m; when the two estimates agree within 1.5x their geometric mean is used.
- **Room** as a rectangle (PCA axes), plus the outline for non-rectangular rooms.
- **Placing an object**: sparse points inside the box; else the box's bottom projected onto the floor (for
  floor-standing classes); else the depth of neighbouring points (wall-mounted things).
- **Merging**: sightings within a class-specific radius are one object; it must be seen in at least 2
  frames (more for the noisy classes, section 10). Output carries the 3D `world` position for the viewer.

### API

| Method | Path | Purpose |
|---|---|---|
| POST | `/auth/signup`, `/auth/login` | accounts (case-insensitive email) |
| GET/POST | `/projects` | list, create |
| POST | `/projects/demo` | add the bundled demo scan (once per user) |
| GET/PATCH/DELETE | `/projects/{id}` | read, rename, delete (also deletes files) |
| POST | `/projects/{id}/upload` | video upload (2 GB, 409 while processing) |
| POST | `/projects/{id}/splat` | attach a splat trained elsewhere |
| GET | `/projects/{id}/status` | live stage and progress |
| GET | `/projects/{id}/objects` | `{detections, meta}` incl. reconstruction |
| GET | `/projects/{id}/analytics` | zones, room, capacity, free space (optional `room_width_m` preview) |
| POST/DELETE | `/projects/{id}/calibrate` | set or reset the real scale |
| POST | `/projects/{id}/ask` | assistant, returns `{answer, focus}` |
| POST | `/files/token`, GET `/files/{id}/{name}?t=` | signed owner-only file links |
| GET | `/health`, `/health/db` | health |

### Frontend

React 19, Vite 8, Tailwind 4, Zustand, React Router 7, Recharts, jsPDF, three.js 0.162 and
`@mkkellogg/gaussian-splats-3d` 0.4.7. Pages: sign in/up, dashboard, project workspace with tabs
**3D viewer, Objects, Floor plan, Analytics, Assistant**.

## 5. Every bug found and fixed

| # | Bug | Fix |
|---|---|---|
| 1 | Backend crashed on import without `email-validator` | added to both requirements files |
| 2 | `pip install` failed on macOS (`ultralytics` vs `numpy 2`) | dropped `ultralytics`; export the model in a throwaway venv (`setup_detector.py`) |
| 3 | Objects/Analytics/Floor plan/Assistant tabs crashed the page (`detections?.reduce is not a function`) | `splitObjects()` unwraps `{detections, meta}` |
| 4 | Analytics fields read from the wrong place; "Not calibrated" forever; PDF without area | read `analytics.area.calibration` |
| 5 | Wrong password: error swallowed by the 401 redirect | skip the redirect for `/auth/` URLs |
| 6 | Videos under about 12 s failed (`vconcat` assertion on the last preview row) | pad the last row with blank tiles; regression test confirmed failing on old code |
| 7 | "Re-upload video" did nothing after a failure | file input rendered unconditionally |
| 8 | Empty JWT secret from `.env.example` allowed forged tokens | empty is rejected |
| 9 | Delete removed only the DB row | also deletes video, frames, models |
| 10 | Restart left scans stuck in "processing" | reset to FAILED on startup |
| 11 | Second upload started a second pipeline; rejected upload overwrote the good video | temp-file write, 409 while processing |
| 12 | Seating capacity: a table capped couch seats; a sink counted as counter | tables only cap chairs |
| 13 | Chat: "how many chairs are in the room" answered with zones; "most free space" named the fullest room; substring matches ("bed" in "bedroom") | whole-word matching, correct rules |
| 14 | Chat used a deprecated model and SDK | `google-genai`, current model name |
| 15 | Portrait phone video squeezed to 405 px wide; x coordinates normalised wrongly | scale by the short side; per-frame width |
| 16 | Heatmap mirrored and misaligned with the dots | same transform for both |
| 17 | PDF only saved if analytics loaded; no pages, chart or plan | two-page report with the same plan drawing |
| 18 | "Try a demo model" always failed on a fresh clone (file git-ignored) | bundled demo scan |
| 19 | Frontend crash/blank when the viewer re-sorted late (stale sort after camera placement) | forced re-sort after every placement, flight and walkthrough |
| 20 | CORS only allowed 5173/127.0.0.1; Vite on 5174 broke everything | any localhost port allowed |
| 21 | Missing detector model failed the whole scan | recorded, scan carries on |
| 22 | Rug reported as a bench, bean bag as a toilet | higher confidence for implausible classes |
| 23 | Zoom on the floor plan captured all scrolling | zoom only with Ctrl/Cmd |
| 24 | Splat viewer rebuilt itself when scan data re-fetched with identical values (broke a running walkthrough) | effect depends on values, not identity |
| 25 | Viewer fade-in stalled where frames are throttled, leaving a blank view | instant reveal |
| 26 | Converter dropped half the model (black holes, noise) | section 9 |
| 27 | Brush never stopped growing in short runs | section 9 |

## 6. Every feature added

### 3D and capture
- Automatic video-to-3D pipeline (above). Photoreal view with orbit, zoom, fullscreen, orientation switch,
  reset view, opening from a real camera pose.
- **Walkthrough**: replays the filmed path; **Show in 3D** flies to an object; floating **labels**.
- **Structure view**: colored point cloud (worst 10% dropped, capped at 60,000 points, about 230 KB), room
  box with faint floor, camera path with an icon per pose, object markers. Needs no GPU, appears as soon as
  the camera path is solved, and is shown instead of an empty panel when training fails.
- **Measure**: click two points on either view for a distance in metres. "I know this length" sets the
  real scale (`2.1`, `210 cm`, `7 ft` are all understood). The scale is stored as metres per
  reconstruction unit on the scan, so the floor plan, room size, assistant answers and PDF all follow it.
  Measurements more than 4x off the estimate, or two points on top of each other, are refused. "Reset"
  restores the estimate. The Analytics "Correct the scale" form saves the same way. Photoreal picking walks
  the splats a ray touches front to back and stops where they add up to mostly opaque.
- **Record**: plays the walkthrough while recording the 3D canvas, saves MP4 (WebM if needed), no buttons
  or labels in the picture. Verified by decoding the file with ffmpeg: H.264, 30 fps nominal, 60 s,
  frames show the real walk through the room.
- Opens on the 3D viewer when a model or structure exists.

### Analysis
- Objects placed in real 3D and merged by distance; zones (DBSCAN, 1.8 m radius), room size, floor area,
  ceiling height, free floor space, seating capacity.
- Doors, windows, lights, cupboards, pictures, curtains via the optional open-vocabulary model
  (`setup_detector.py --open-vocab`); treated as structure, not furniture (no floor space, no zone).
- Assistant: rules offline, or Gemini / Claude / any OpenAI-compatible server including Ollama; history;
  grounded on real scene data; points at objects ("Where is the TV?" then **Show in 3D**); understands
  door/window/light/cabinet/shelf/picture/curtain by name; positions follow the saved scale.

### Floor plan (redesigned)
Clean rectangle walls with thick round corners and a soft shadow; furniture at typical real size
(chair 0.46 m, couch 1.9 m, TV 1 m ...) colored by purpose; quiet dot grid; dimension chips, area figure,
scale bar and a "scale estimated" note; zones as tinted areas; camera path, density map and names as
toggles; click an object for confidence, frames seen and position, with **Show in 3D**; drag to pan,
zoom buttons, Ctrl/Cmd + scroll, double-click to fit; legend with counts. Doors are cut into the wall with
their swing, windows drawn as glazing, snapped to the nearest wall within 1 m. The PDF draws the same plan.

### App shell and workspace
Drafting-sheet visual identity; sign in with an animated isometric wireframe room; dashboard with
thumbnails, status pills, plain-language errors, delete confirmation, skeletons, first-run guide, live
updates; upload by drag and drop or "Record with camera" on phones; processing screen with real stage and
percentage; title-block stats; Objects tab with counts and "Show in 3D"; Analytics with a chart; PDF report.

### Operations
`install_brush.py`, `setup_detector.py`, `doctor.py` (with `--gpu-test`), `reanalyze.py`, `retrain.py`,
`export_demo.py`, `evaluate.py`, `export_open_vocab.py`. The bundled demo scan. README with Windows and
macOS/Linux quick starts and a troubleshooting section.

## 7. Security and privacy

- **Files were public.** `/media` and `/splats` served every user's video and model to anyone with a URL.
  Replaced by `/files/<project>/<name>?t=<token>`: a 30-minute token scoped to "files", valid only for files
  the requesting user owns (a login token is not accepted).
- No server file paths in API responses (only `has_video` / `has_splat` / `has_structure`).
- Unhandled errors no longer leak exception text.
- Empty JWT secret rejected; emails case-insensitive; uploads written via a temp file and refused while
  processing; 2 GB limit as in the PRD.
- **LLM privacy**: only `LLM_PROVIDER` + `LLM_API_KEY` choose an AI service. Shell keys such as
  `ANTHROPIC_API_KEY` are ignored on purpose.
- Calibration endpoints enforce ownership (404 for another user, 401/403 without a token); inputs are
  validated (finite numbers, bounded lengths).
- The demo scan is copied per user and the bundled files are never edited or deleted.

## 8. Small and Windows GPUs

Written after the friend could not see the 3D model on an RTX 3050 laptop. I could not reproduce it, so
these are the likely causes, each fixed:

- **No trainer installed.** Brush is a separate download that the old README barely mentioned. Now
  `install_brush.py` does it (checksum-verified) and `doctor.py` checks it.
- **Trainer memory.** Brush trains with `--sh-degree 0` (the browser viewer discards view-dependent colour
  anyway), caps splats and image size (`SPLAT_MAX_SPLATS`, `SPLAT_MAX_RESOLUTION`), asks for the fast GPU
  on two-GPU laptops, and retries once with much lighter settings if it crashes.
- **Errors people can act on** for: out of memory, no usable graphics adapter, a missing Windows runtime
  library, a missing trainer.
- The trainer is found even if a Windows zip tool nested it in folders.
- **Browser without WebGL2 or on the wrong GPU**: the viewer detects it and explains how to turn on
  hardware acceleration and pick the high-performance GPU.
- **Blank first frame** on slow GPUs (stale splat sort) fixed; the doctor's `--gpu-test` trains a tiny model
  (about 1.5 MB of photos) in 10 to 60 seconds and reports success or the specific failure.
- **Brush installer** (after a download error on the Victus): resumes dropped downloads (HTTP Range, up to 8
  retries), retries with the `certifi` bundle if Windows certificate validation fails, accepts a zip saved
  in `backend/tools/` or `--file`, unpacks the real Windows zip (which has `brush_app.exe` at its root)
  into its own folder, tolerates BOMs/`*file`/CRLF in checksum files, deletes a download whose checksum
  does not match, and prints the manual steps on any failure. Tested against a local fake GitHub.
- **Demo scan**: a 22 MB photoreal model plus its analysis, so the app can be shown with no GPU at all.
- Detector missing, detection crashed, or trainer missing: the scan still completes and says what to do.

**Not verified on the real machine.** Everything above was tested on a Mac.

## 9. The quality investigation (numbers)

You sent two screenshots of a blurry, smeared model and said the quality could improve. Instead of
guessing, I measured.

### Method
1. Re-built the playroom training set and trained with Brush holding out every 8th image (26 of 207).
2. Scored two things against those unseen photos: **Brush's own render**, and **the app's viewer** (I wrote
   a throwaway page that loads the exact converted `.splat` into the same viewer library and renders the
   held-out camera poses at the photo size). The second one is what you actually see.
3. Metrics: PSNR in dB (higher is better), SSIM, and a sharpness ratio (Laplacian energy against the photo).

### Finding 1: the converter threw away half the model
Brush builds walls, ceilings and backgrounds from hundreds of thousands of faint splats. On this scan 46%
of all splats are under 5% opacity and 75% are under 10%. The converter dropped everything under 5% and
the largest 1%, leaving black holes behind the stairs and noisy rainbow edges.

| Converter filter (same trained model, browser viewer) | PSNR | SSIM |
|---|---|---|
| Old: opacity under 5% and largest 1% dropped | 22.60 | 0.825 |
| Opacity cut alone (5%) | 22.38 | 0.871 |
| Size cuts alone | 24.52 | 0.870 |
| No filtering at all | 25.92 | 0.905 |
| Opacity 0.02 only | 25.92 | 0.905 |
| **New: opacity 0.02, largest 0.05%, farthest 0.1%** | **26.00** | 0.901 |

The viewer ignores anything under about 2% opacity itself (its `splatAlphaRemovalThreshold` of 5/255), so
keeping less than that gains nothing (lowering the threshold to 1 scored 25.86).

### Finding 2: short runs were never polished
Brush's default growth stops at step 15,000, so any run shorter than 30,000 steps keeps adding splats until
the very end. The new schedule stops growth at 55% of the run and uses a lower growth threshold (finer
detail).

### The training experiments (12,000 to 30,000 steps)

| Run | Steps | Time on M4 | Splats after convert | Brush render PSNR | **Browser viewer PSNR** | Viewer SSIM |
|---|---|---|---|---|---|---|
| 3,000 steps (baseline probe) | 3,000 | 3 min | | 25.76 | | |
| Old default | 12,000 | 11.6 min | 672k | 29.07 | 26.00 | 0.901 |
| Growth stops at 6,000 | 12,000 | 12.5 min | 176k | 28.56 | 26.40 | 0.906 |
| Lower threshold, stop 8,000 | 12,000 | 13.5 min | 413k | 28.94 | 26.50 | 0.906 |
| Lower threshold, stop 9,000 | 12,000 | 14 min | 552k | 28.99 | 26.52 | 0.903 |
| Same, no position noise | 12,000 | 14 min | 545k | 29.12 | 26.57 | 0.905 |
| **Lower threshold, stop 10,000** | **18,000** | **25 min** | 722k | 29.10 | **27.37** | 0.905 |
| Brush default schedule | 30,000 | 47 min | 980k | 29.27 | 27.97 | 0.906 |

All "Browser viewer" scores use the new converter, so they are comparable with each other. The first row's blanks mean it was only a quick probe.

Brush's own render barely moves with steps (+0.2 dB from 12k to 30k) while the browser view gains about 1
dB per 6,000 steps. I do not know why; it is just what the measurement shows.

### Tried and rejected (no measurable gain)
- Storing colours at 1/1.5 and restoring the gain in the shader (30% of splats have a colour channel above
  1.0 that the 8-bit `.splat` clips): 26.05 vs 26.00 dB.
- Finer opacity steps at the low end (square-root encoding with a shader patch): 26.05.
- Viewer antialiasing: 25.95. Larger 2D kernel (0.6): 25.94.
- Training without Brush's position noise: same as with it.
- Perceptual (LPIPS) loss: this Brush build crashes with it.
- Spherical harmonics (sh-degree 3): pointless, the `.splat` format keeps only the base colour.

### The result
New defaults: `SPLAT_QUALITY=high` = 18,000 steps with the growth schedule. Presets:

| Preset | Steps | About (M4) | Browser view |
|---|---|---|---|
| fast | 7,000 | 8 min | not measured |
| balanced | 12,000 | 14 min | 26.5 dB |
| **high (default)** | 18,000 | 25 min | 27.4 dB |
| max | 30,000 | 47 min | 28.0 dB |

The demo scan was retrained with all of this. On the camera positions it was trained on:
**26.1 dB / SSIM 0.884 to 28.9 dB / 0.932**, black hole gone, 698,778 to 714,512 splats, 22.4 to 22.9 MB.
Side by side with the photo: [`docs/model-quality.jpg`](model-quality.jpg).

`scripts/retrain.py <project-id>` rebuilds an older scan with the current settings; scans created before
this change keep their old model until it is run. The training time limit was raised from 60 to 150
minutes, since a slow laptop GPU needs well over an hour for the high preset.

**Not measured:** other rooms, the friend's GPU, and why the browser view still scores about 3 dB below
Brush's own render (the two agree with each other at 29.5 dB, so the viewer's output is just noisier).
The input is 720p frames, so close-ups stay soft whatever the training does.

## 10. Detection: what works and what does not

### The detectors
YOLOv8s (ONNX, CPU) is the default; YOLOv8n is a fallback. An optional **YOLO-World** model, exported with
`python scripts/setup_detector.py --open-vocab` (about 370 MB of one-time downloads, needs Git, AGPL/GPL
licence), adds: door, window, light (ceiling light, lamp), counter, cabinet, shelf (bookshelf), picture,
curtain. The detector keeps the best-scoring class per box.

### What was tuned, in order
1. Global threshold 0.25: found cabinets, a light and a picture on the playroom, no doors or windows.
2. The model scores a clear door at 0.06 to 0.15 where a chair scores about 0.5, so doors and windows got
   their own lower thresholds (the network is asked for the lowest threshold any class needs, then each
   class is filtered by its own).
3. Open-vocabulary classes must stay in view for more frames: 3 for door and window, 4 for light, counter,
   cabinet, shelf, picture, curtain. Wide things merge over a larger radius (window 1.2 m, door 0.9 m).
4. Reviewing the actual detections (crops of the best sighting of each) showed the problem: of four
   "cabinets", only the bookcase (0.60) was a cabinet; a desk (0.46) and a toy side table (0.37) were
   wrong. The single "window" was a wall book rack (0.17). The real window/door scored 0.11 to 0.13.
   **Confidence cannot separate them.** So the app is now precision-first: cabinet, counter, shelf need a
   mean confidence of 0.5; door and window need 0.2 (and the network is asked for them at 0.10 or more).
5. On the playroom sample, the demo scan now shows: 2 chairs, 1 TV, 1 cabinet (the bookcase), 1 picture
   (the chalkboard). No doors or windows, on purpose.

### Prompt wording (corrected in section 14)
Six window wordings ("window", "a window", "window with glass panes", "window frame", "glass window in a
wall", "transom window") all scored 0.09 to 0.14 and all produced false hits. For doors the wording
**does** matter in a probe model: "white door" scored 0.20 on the curtained doorway that plain "door"
missed, and "cupboard door" scored up to 0.65 on the real panelled door under the stairs but just as high
on cupboards and bookcases. The shipped prompts were not changed; adding "white door" and "wooden door" as
extra prompts for `door` is the obvious next experiment.

### Counting and placement (before and after)
Before: detections merged by screen position, so a chair seen from two angles counted twice and two
different chairs could merge. Now each sighting is placed in 3D and merged by metric distance, and a
one-off false alarm in a single frame is dropped. Rare, easily confused classes (toilet, bench, sink,
refrigerator, oven, microwave) need higher confidence. On the playroom the app finds 2 chairs and a TV;
none of this was checked against a hand count on other scenes.

## 11. Tests

98 backend tests pass (the count grew 12 to 17 to 22 to 34 to 44 to 54 to 57 to 82 to 85 to 98 over the session).

| File | Tests | Covers |
|---|---|---|
| `test_unit.py` | 14 | calibration math, capacity rules, room clustering, preview regression |
| `test_engine.py` | 13 | frame extraction, converter (floaters, cap, faint haze kept), trainer retry, growth schedule, quality presets, error messages |
| `test_spatial.py` | 9 | synthetic room of known size under a random rotation (up within about 1 degree, size within about 3%), 3D merging, vote and confidence rules, merge radii, room box |
| `test_assistant.py` | 13 | provider request shapes with fake HTTP, ambient-key privacy regression, focus, door/window answers with the saved scale |
| `test_scale.py` | 15 | two-point and room-side calibration, persistence, reset, refusal of implausible input, ownership, structure vs furniture |
| `test_detector.py` | 3 | per-class thresholds |
| `test_installer.py` | 9 | resume after a dropped connection, wrong checksum, hand-saved archive, real zip layout |
| `test_demo.py` | 2 | demo added once, private, survives delete |
| `test_api_flow.py` | 4 | end to end (skipped without the detector model) |

Frontend: `oxlint` and `vite build` are clean. There is **no frontend test suite**, so the viewer, Measure,
Record and floor-plan drawing were verified by driving the app in a browser and decoding the recorded file,
not by automated tests.

## 12. Scripts and settings

| Script | What it does |
|---|---|
| `install_brush.py` | download, verify and unpack the Brush trainer for this OS |
| `setup_detector.py` | export the detector (`--open-vocab` for doors/windows/lights, `--force`) in a throwaway venv |
| `doctor.py` | check Python, packages, Node, FFmpeg, detector, open-vocab model, Brush, GPUs, `.env`, folders, demo; `--gpu-test` trains a tiny model |
| `reanalyze.py <id>` | re-run detection and analysis, rebuild the structure file, without retraining |
| `retrain.py <id>` | retrain the photoreal model with current settings and converter |
| `export_demo.py <id> [name]` | turn a finished scan into the bundled demo (drops any user calibration) |
| `evaluate.py <id> truth.json` | compare a scan with a tape measure and hand count, print a Markdown report |
| `export_open_vocab.py` | the YOLO-World exporter (run by `setup_detector.py --open-vocab`) |

Settings in `backend/.env`: `DATABASE_URL`, `JWT_SECRET_KEY` (required), `GEMINI_API_KEY` / `GEMINI_MODEL`,
`LLM_PROVIDER` / `LLM_API_KEY` / `LLM_MODEL` / `LLM_BASE_URL`, `SPLAT_QUALITY` (fast, balanced, high, max),
`SPLAT_TRAIN_STEPS` (overrides the preset), `SPLAT_MAX_SPLATS`, `SPLAT_MAX_RESOLUTION`, `MAX_UPLOAD_MB`,
`CORS_ORIGINS`, `YOLO_ONNX_PATH`, `BRUSH_PATH`. For a 4 GB card: `SPLAT_MAX_SPLATS=300000`,
`SPLAT_MAX_RESOLUTION=800`.

## 13. All 20 commits

On branch `improvements`, all pushed to `main`.

| # | Commit | Date | What |
|---|---|---|---|
| 1 | `52f283d` | 8 Oct | Initial commit (the friend's project) |
| 2 | `f04415a` | 8 Oct | The 3D engine: camera poses, objects placed in 3D, splat training |
| 3 | `353ad80` | 8 Oct | Wire the pipeline into the API; fix crashes; harden security |
| 4 | `c47cc11` | 8 Oct | Assistant: any language model, history, "show me in 3D" |
| 5 | `e289c4e` | 8 Oct | App shell redesign: drafting-sheet look, sign-in, dashboard |
| 6 | `b30f17f` | 8 Oct | Project workspace: 3D twin, floor plan, analytics, assistant UI |
| 7 | `16002ad` | 8 Oct | Docs, setup, limits, `evaluate.py` (pushed: `52f283d..16002ad`) |
| 8 | `aa19c4d` | 9 Oct | 3D model reliable on small and Windows GPUs |
| 9 | `8ca8add` | 9 Oct | Bundled demo scan |
| 10 | `033f33b` | 9 Oct | One-command setup and the doctor |
| 11 | `f8eadff` | 9 Oct | Show the 3D model reliably and explain it when it cannot be shown |
| 12 | `3881300` | 9 Oct | Doctor hints; skip the end-to-end test without the detector (pushed: `..3881300`) |
| 13 | `b437c97` | 9 Oct | Brush installer survives bad connections (pushed) |
| 14 | `8de44bb` | 9 Oct | Export the 3D structure recovered from the video |
| 15 | `655b5f8` | 9 Oct | Structure view (pushed) |
| 16 | `f63b6ff` | 9 Oct | Floor plan redesign |
| 17 | `f964535` | 9 Oct | Measure, saved scale, Record walkthrough, viewer robustness |
| 18 | `0b82c1e` | 9 Oct | Doors and windows in the floor plan, per-class detector thresholds |
| 19 | `a37709a` | 9 Oct | Sharper 3D model: converter, growth schedule, presets, `retrain.py`, demo retrained |
| 20 | `189be67` | 9 Oct | Show only the cabinets, doors and windows the detector is fairly sure of (pushed: `655b5f8..189be67`) |

Push history: the first two pushes of mine were blocked by the permission check and respected; you ran
`16002ad` yourself, and later said "push it" for the rest.

## 14. Mistakes I made and corrections

Being straight about these matters more than looking tidy:

- **LLM key privacy bug (caught and fixed).** My first assistant code auto-selected the shell's
  `ANTHROPIC_API_KEY`, which would have sent scan data to an AI service you never chose. Fixed, with a
  regression test.
- **Test-suite hang (fixed).** I patched `time.sleep` globally in a test and never undid it, so the suite
  hung. Moved into a fixture with `monkeypatch`.
- **Scroll-hijacking zoom (fixed).** The first floor-plan zoom swallowed page scrolling.
- **A wrong claim about doors and windows (corrected here and in the README).** I told you, in a commit
  message and in my last reply, that I had tried "six window and seven door phrasings" with no difference.
  That was half true: I scored the six window wordings (all 0.09 to 0.14), but I had only *exported* the
  door probe and not scored it. Scoring it just now showed door wording does matter (section 10). The
  README sentence is corrected in the working tree; the wrong sentence remains in the wording of commit
  `189be67`, which is already pushed.
- **An earlier claim that the demo finds "the transom window".** After the detector was tuned, the one
  "window" the model reported was actually a wall book rack. I removed it by making doors and windows
  precision-first, and said so, but my first commit message for that feature was too optimistic.
- **Brush's progress.** I first documented about 16 minutes for 12,000 steps; a clean run on an idle M4 took
  11.6 minutes. Times in this document are the measured ones.
- **A recording that did not move.** My first recorded walkthrough was a static shot. I could not
  reproduce it afterwards; the likely cause (the viewer rebuilding itself mid-walkthrough) is fixed, and
  later recordings moved correctly. Treat Record as verified on this machine, not exhaustively.
- **Testing pitfalls on my side (not bugs in the app):** the in-app browser pane shows a stale screenshot
  by one action and pauses animation when hidden, which looked like a blank-viewer bug until I traced it;
  a `sed` with special characters failed on macOS and I switched to Python; two tool calls used the wrong
  tool name and did nothing.

## 15. Limits and what was not verified

**Not verified at all**
- Windows and the RTX 3050 / HP Victus: no part of the Windows install, trainer, doctor or viewer path
  was run there.
- A real phone recording. Everything used the public "playroom" photos made into a video.
- Live Gemini, Claude or Ollama answers (no keys or local model here); only fake-server tests.
- Detection accuracy against hand counts on other scenes.

**Known weaknesses, stated plainly**
- **Sizes are estimates** (phone assumed held at 1.4 m). Measuring in 3D or entering a tape measurement
  fixes the scale; on synthetic rooms the estimate is about 2 to 3% off, real footage will be rougher.
- **Doors and windows are unreliable**: precision-first, so many real ones are missed. Cabinets, counters
  and shelves are fuzzy classes.
- **The floor plan walls are a fitted rectangle** (L-shaped rooms are drawn as rectangles unless clearly
  non-rectangular); furniture is drawn at typical size, axis-aligned.
- **Labels are not occluded** by walls or furniture.
- **The Structure view is a sparse point cloud**, not a mesh.
- **Close-ups stay soft**: the input is 720p video frames.
- **The browser view is about 3 dB noisier than Brush's own render** (unexplained).
- The 22 MB demo comes from a public dataset (credited in `backend/demo/README.md`), not your own room.
  For the final submission, scan a real room and run `export_demo.py`.
- Existing scans keep their old (blurrier) 3D model until `retrain.py` is run on them, and users who
  already added the demo scan need to delete it and add it again to get the new one.
- No Docker setup; SQLite in development (Postgres/S3 would be needed to deploy); `PLAN.md` still
  describes Postshot and is out of date.
- Licences: `ultralytics` and YOLO-World are AGPL/GPL (fine for an open-source academic project, check
  before a closed product); Brush is Apache-2.0.

## 16. What the friend needs to do

After `git pull` on `main`, in the `backend` folder with the venv active (Windows PowerShell shown):

```powershell
pip install -r requirements.txt
python scripts/install_brush.py          # the 3D trainer (resumes if the download drops)
python scripts/setup_detector.py         # one-time detector export
python scripts/setup_detector.py --open-vocab   # optional: doors, windows, lights (370 MB, needs Git)
python scripts/doctor.py --gpu-test      # checks everything and trains a tiny model in about a minute
```

- No GPU or short of time: press **Demo scan** on the dashboard.
- If the doctor reports out of memory: put `SPLAT_QUALITY=balanced`, `SPLAT_MAX_SPLATS=300000` and
  `SPLAT_MAX_RESOLUTION=800` in `backend/.env`.
- If the browser shows a graphics message, follow it (turn on hardware acceleration; on a two-GPU laptop
  choose the high-performance GPU for the browser in Windows Settings).
- Film a slow 30 to 60 second walkthrough of a furnished room for the real test, then run
  `python scripts/evaluate.py <project-id> truth.json` against a tape measure and a hand count, and put the
  table in the report. This probably earns more marks than any extra feature.

## 17. Ideas not done

From the list you were given (effort S = hours, M = a day or two, L = a week or more). Done: Measure,
Record, doors/windows/lights.

- Find anything by describing it (CLIP over the frames), M to L.
- Furniture what-if: drag furniture on the plan and watch capacity and free space update, M.
- First-person walk with W A S D, M.
- Real wall detection from the point cloud (L-shaped and multiple rooms), L.
- Room labels from a vision-language model, M.
- Mobile capture app (Flutter) or an installable web app with filming guidance, M to L.
- Cloud storage, Postgres and a job queue, L.
- Restaurant clearance check (90 cm aisles, route to the exit, occupancy estimate), M.
- Listing text and a shareable read-only link; pinned notes; re-scan comparison over time.
- Exports: floor plan as SVG/PNG/DXF, objects as CSV, model as PLY, S.
- A scan quality score after upload (frames placed, blur, coverage), S to M.
- A metric depth model to check the 1.4 m assumption, M to L.
- A CUDA trainer option for NVIDIA laptops, M.
- **An accuracy study on 4 or 5 real rooms** (the script exists), S but needs real rooms.
- Docker Compose and GitHub Actions; account basics (email verification, password reset, login rate
  limiting, delete my data); architecture, ER and sequence diagrams and a slide deck.
- Try "white door" and "wooden door" as extra door prompts, and a larger YOLO-World model.

## 18. Appendix: every message you sent

In order, lightly trimmed.

1. "have a look to this project my friend is making for mca, tell me all not working thing and how I can fix it, first read this" (the GitHub link)
2. "first run it locally so I can check it"
3. The full PRD plus a screenshot of a failed scan: "this was my project idea but it is made some like this, check all thing and tell me how to improve, also make the ui more good and check if some thing like this exists"
4. "copy it and the 3d model generate is not good and realistic, make it something realistic and start improving, you are telling the things"
5. (choice) "Download a public sample (~650 MB)"
6. "AI Digital Twin Generator is a platform that transforms a simple smartphone video into an interactive 3D digital representation of an indoor space... have to followed this problem statement"
7. "ok commit all the changes in 6 commit and tell me what things my friend need to do"
8. "man push them to main directly"
9. "done I am now the contributor so push it"
10. (terminal) `git push origin improvements:main`, then again from the project folder, which succeeded
11. "my friend ran the project in the victus laptop 3050 trx. he was saying he couldn't see the 3d model and all, have a look and I want also good enough 3d model to show in project"
12. "push it to main"
13. "in victus I am getting some error while downloading brush"
14. "push them"
15. "I think according to my problem statement a 3d structure is generate by the video, can you check if yes generate a demo so I can see it"
16. "ok push it to main"
17. A screenshot of the floor plan: "working great, we can make the floor plan modern and great, think"
18. "ok now tell me what all things I can add on this"
19. "plan and do 1, 2, 3 you have told"
20. Two screenshots of the viewer: "I think we can improve the quality"
21. "ok push them to main"
22. "ok now generate a whole session of this project md file. I want all the things we have done in this project. I want all things" (this file)

---

## 19. Follow-up (10 October): your own phone video, and its quality

After the session log above you asked me to use a real phone video ("WhatsApp Video 2026-10-09 at 22.17.51.mp4")
and later said the quality of its 3D model was not good. What I did and found:

**The video.** 9.8 seconds, 480x854 (WhatsApp shrinks and re-compresses), 30 fps, a pan across a room (monitors,
chair, door, wall hanging) filmed by turning in place. Uploaded through the real app on the local server, signed
in as `demo@twindemo.dev`.

**What the pipeline did.** 39 frames at 4 per second, all 39 placed in 3D, 2,058 3D points (the playroom has about
17,000), 108,611 splats (3.5 MB), 3 chairs and 1 TV detected (not checked against the real room). The app logged
"No clear floor or ceiling was found", so its 6.6 x 3.0 m room estimate is unreliable.

**Why it looked smeared (measured).** Depth comes from seeing a point from different places. I measured the median
angle at which each 3D point is seen from: **5.9 degrees** for this pan against **24.8** for the playroom walk
(camera spread over scene depth 0.58 against 2.27). The model is right from the filming spot and streaks from
anywhere else. This is a property of the footage, not of the training.

**What I changed.**
- `spatial.triangulation_angle_deg()`, stored as `parallax_deg` / `low_parallax` in the scan data, and a note in the
  Analytics tab when it is under 10 degrees (`LOW_PARALLAX_DEG`).
- **Look-around mode** in the photoreal viewer for such scans: the camera stays where the phone stood and only
  turns (no pan, no dolly, no click-to-recentre; the wheel changes the field of view; Show in 3D turns towards an
  object instead of flying to it) with a banner that explains it. Areas the phone never pointed at are black.
- **Short videos are sampled more densely** (`extractor.choose_fps`: about 240 frames, between 4 and 12 per
  second). The end-to-end API test no longer trains a model (it would now reach training with the synthetic video).

**Experiments, scored on frames the model never saw** (the first and last second of the pan were held out, the
browser viewer's own renders compared with the photos):

| Run | Frames used | Time | Held-out PSNR | SSIM |
|---|---|---|---|---|
| Baseline: 18,000 steps, 4 fps | 31 | 15 min | 18.83 dB | 0.799 |
| 7,000 steps | 31 | 5 min | 16.24 dB | 0.786 |
| Scale-loss weight 1e-6 (penalise big splats) | 31 | 14 min | 16.29 dB | 0.766 |
| **12 fps, 18,000 steps** | 83 | 21 min | **19.93 dB** | **0.845** |

Structure-from-motion on the same video: 720 px frames at 4 fps placed 39 of 39; native 480 px frames placed 23 of
36 (12 fps: 63 of 117), so frames are still scaled up to 720 px. 12 fps at 720 px placed 104 to 107 of 117 with 4,058
to 5,782 points (the camera-path step is not fully repeatable between runs). Frame spacing decides whether a camera
path is found at all: on the playroom, every 8th frame placed 2 of 28, every 6th 8 of 38, every 4th 54%, every 3rd
83%, every 2nd 89%.

**What this does not fix.** A pan from one spot can never become a walkable 3D room. The honest advice stays: film
while walking along the walls for 30 to 60 seconds, send the original file instead of a WhatsApp copy, light the
room, and use the 1x camera.

**Side findings.** The original video file became unreadable to my shell part-way (macOS privacy permission for
Downloads), so later experiments used the copy the app had stored. A test helper of mine deleted its own dataset
because an experiment and its folder shared a name; I re-prepared it and renamed the run. `deregister_image` is not
in this pycolmap version (`deregister_frame` is).

---

## 20. Photos instead of a video (10 October)

You asked whether adding several photos of a place could also produce a 3D model, and then to build it. Answer: yes,
the engine only needs overlapping pictures; the demo scan itself came from 224 photos. What was missing was the upload.

**Built**
- `POST /projects/{id}/photos` (multipart field `files`, repeated): 15 to 300 JPG, PNG, WebP or HEIC photos, 80 MB each,
  2 GB in all. Refuses too few, too many, wrong types, another user's scan, and a scan that is still processing. File
  names are made safe, so `../../evil.jpg` cannot leave the folder. A scan comes from one source: the latest upload
  (video or photos) replaces the other. `has_photos` joins `has_video` on the project.
- `services/photos.py`: applies the phone's rotation flag, scales to 720 px on the short side (also upwards, like video
  frames: native-size small frames registered far worse in the earlier experiment), keeps the order of the file names
  (IMG_2 before IMG_10), skips unreadable files and, if fewer than 15 remain, fails the scan saying how many and why.
- Mixed shapes (portrait and landscape) get a camera each (COLMAP `PER_IMAGE`) instead of one shared camera. Checked on
  70 photos of two shapes: 63 placed in 3D, and the trainer accepts the result.
- HEIC via `pillow-heif` (added to the requirements; the doctor reports whether it is installed).
- Interface: **Choose photos** and dropping several photos next to **Choose video**; a message before anything is sent
  when fewer than 15 or an unsupported file is chosen; separate tips for photos; the processing screen and the status
  pill say photos; the button to replace a scan now says "Upload new video or photos".
- 13 new tests (98 in all): resizing, rotation flag, name order, unreadable files, HEIC, mixed shapes, the API rules
  above, and the pipeline running from photos to DONE.

**Verified in the real interface.** A browser driven with real files: 5 photos were refused on the page with "Choose at
least 15 photos (you chose 5)"; 112 photos cut from the playroom footage uploaded and were processed end to end: 112
frames, 99 placed in 3D, 11,431 3D points, depth information 28.7 degrees (a walk, so normal orbiting), room
4.67 x 3.58 m (the video gave about 4.7 x 3.7), 587,436 splats (18.8 MB), 3 objects, photoreal model shown in the viewer.

**Not verified.** A genuinely separate set of real photos (these came from video frames, so they are as sharp and as
evenly spaced as a good set); HEIC from a real iPhone; photos taken at several zoom levels.

**A mistake worth knowing about.** My first run of the 112 photos was marked failed ("interrupted by a server restart")
because I edited a Python file while the dev server ran with `--reload`, which restarts it and ends the running job.
I restarted the server without `--reload`, re-uploaded, and that is the run described above. Do the same when you
process long scans during development.

**Pulling your friend's changes.** `git fetch` found nothing new on `origin/main` (still `189be67`), so there was
nothing to merge.
