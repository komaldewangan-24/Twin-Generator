# AI Digital Twin Generator — Descriptive Phase-Wise Build Plan

> **Project:** Convert a smartphone walkthrough video into an interactive 3D digital twin with AI object detection, floor plans, analytics, and a natural-language assistant.
> **Constraints:** Solo developer | ~2 months | NVIDIA RTX 2060+ | $0 budget | MCA minor project evaluation.
> **How to use this document:** Work phases strictly in order. Each phase has a "Definition of Done" — do not start the next phase until it passes. Concepts are explained inline so you can defend every choice in your viva.

---

## Master Architecture (What You Are Building)

```
┌──────────────────────────── YOUR PHONE / LAPTOP BROWSER ───────────────────────────┐
│  React App                                                                          │
│  Login → Dashboard → Upload Video → Live Progress → [3D Viewer | Floor Plan |      │
│  Object List | Analytics | AI Chat]                                                 │
└───────────────────────────────────────┬─────────────────────────────────────────────┘
                                        │ REST API (JSON over HTTP, JWT protected)
┌───────────────────────────────────────▼─────────────────────────────────────────────┐
│  FastAPI Backend                                                                    │
│                                                                                     │
│  Auth Module ──► Project CRUD ──► Upload Handler ──► Pipeline Orchestrator          │
│                                                              │                      │
│   ┌──────────────────────────────────────────────────────────┘                     │
│   ▼ BACKGROUND PIPELINE (runs async after upload completes)                       │
│   1. FFmpeg        → extracts ~200 frames from video                              │
│   2. Splat Trainer → frames → 3D gaussian splat (.ply)                            │
│   3. YOLOv8        → frames → object detections                                   │
│   4. Aggregator    → detections → objects.json (counts + positions)               │
│   5. Algorithms    → calibration → room clustering → seating capacity             │
│   6. Finalize      → save results to PostgreSQL, set status = DONE                │
└──────────┬──────────────────────────────────────────────────────────────────────────┘
           │
     ┌─────▼──────┐      ┌──────────────────┐      ┌──────────────────┐
     │ PostgreSQL │      │ Gemini API (LLM) │      │ Local disk       │
     │ (Neon free)│      │ answers questions│      │ videos/frames/   │
     └────────────┘      └──────────────────┘      │ splats storage   │
                                                   └──────────────────┘
```

**Key design decision (memorize for viva):** The AI assistant never watches the video. All intelligence flows through one structured file (`objects.json`) produced by the pipeline. That single artifact powers the floor plan tab, the analytics dashboard, AND the chat assistant. One data source → three features. This is why the system stays consistent and fast.

---

# PHASE 0 — Foundation & Environment Setup

**Duration:** Days 1–3
**Plain-language goal:** Get every tool installed and both apps booting with an empty database, so no later day is wasted fighting setup issues.

### Why this phase exists
Most student projects die in week 5 because of environment chaos — different package versions on different days, secrets committed to Git, database passwords lost. Phase 0 prevents all of that in one afternoon.

### Concept: what each piece does
| Tool | Role |
|---|---|
| Python venv | Isolated sandbox for backend packages so system Python stays clean |
| Node + Vite | Build tool that scaffolds and hot-reloads the React frontend |
| PostgreSQL (Neon.tech) | Free cloud-hosted relational database — survives laptop reinstalls, looks professional ("cloud database") in your report |
| Git/GitHub | Version history; also proof of consistent work for evaluators |

### Step-by-step tasks
1. `git init` inside `C:\Users\Hp\Desktop\vision`. Create `.gitignore` immediately containing: `node_modules/, .env, __pycache__/, *.pyc, venv/, storage/uploads/, storage/splats/, dist/`.
2. Create Neon account → new project → copy connection string → save to `backend/.env` as `DATABASE_URL=postgresql://...`. Never hardcode it anywhere else.
3. Backend scaffold:
   ```
   backend/
   ├── app/
   │   ├── main.py              # FastAPI app factory, CORS, router mounting
   │   ├── core/config.py       # reads .env via python-dotenv
   │   ├── core/database.py     # SQLAlchemy engine + SessionLocal
   │   ├── models/              # ORM table classes
   │   ├── schemas/             # Pydantic request/response shapes
   │   ├── api/                 # auth.py, projects.py, pipeline.py, chat.py
   │   ├── services/            # extractor.py, detector.py, reconstruct.py,
   │   │                        # calibrate.py, segment_rooms.py, capacity.py
   │   └── utils/security.py    # hashing + JWT helpers
   ├── storage/
   │   ├── uploads/             # incoming videos + extracted frames
   │   └── splats/              # trained .ply/.splat artifacts
   └── requirements.txt
   ```
4. Install backend deps: `fastapi uvicorn[standard] sqlalchemy psycopg[binary] alembic python-jose[cryptography] passlib[bcrypt] python-multipart aiofiles opencv-python-headless ultralytics numpy pillow python-dotenv google-generativeai pytest httpx`
5. Install PyTorch WITH CUDA: `pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121`. Verify GPU visible: `python -c "import torch; print(torch.cuda.is_available())"` must print `True`.
6. Frontend scaffold: `npm create vite@latest frontend -- --template react`, then add: `react-router-dom axios zustand tailwindcss three @react-three/fiber @react-three/drei @mkkellogg/gaussian-splats-3d recharts jspdf`
7. System installs: FFmpeg (add to PATH, verify with `ffmpeg -version`), Node 20+, Git, and Postshot from jawset.com (Windows beta, needs NVIDIA GPU).
8. Create `/health` endpoint returning `{"status":"ok"}`; make React home page call it and display result.

### Pitfalls to avoid
- Don't skip the CUDA torch step — CPU-only torch makes YOLO ~20x slower.
- Commit `.env.example` (with dummy values) but never `.env`.

### Definition of Done
- `uvicorn app.main:app --reload` serves `/health` ✅
- React dev server renders page that successfully fetches `/health` ✅
- `torch.cuda.is_available()` → True ✅
- First commit pushed to GitHub ✅

---

# PHASE 1 — Authentication & Project Management

**Duration:** Week 1 → mid Week 2
**Plain-language goal:** Users can register, log in, and manage their list of scan projects. No scanning features yet — just the locked front door and the filing cabinet.

### Concept: how JWT auth works (viva favorite)
1. User posts email + password to `/auth/login`.
2. Server verifies password against stored **bcrypt hash** (we never store real passwords).
3. Server creates a **JWT** — a cryptographically signed token containing the user id + expiry.
4. Browser sends this token in the `Authorization: Bearer <token>` header on every request.
5. Server validates signature → knows who's asking without a session database.

Why chosen over sessions: stateless, works naturally with mobile apps later, industry standard.

### Database schema (design this properly — ER diagram material)

**users**
| column | type | notes |
|---|---|---|
| id | UUID PK | default gen_random_uuid() |
| email | VARCHAR UNIQUE | login identifier |
| password_hash | VARCHAR | bcrypt |
| created_at | TIMESTAMP | |

**projects**
| column | type | notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK→users.id | ownership link |
| name | VARCHAR | user-given label |
| status | ENUM | UPLOADED / EXTRACTING / TRAINING_3D / DETECTING / DONE / FAILED |
| error_message | TEXT NULL | reason when FAILED |
| scan_date | TIMESTAMP | shown on dashboard |
| thumbnail_path | VARCHAR NULL | preview image |

Later phases add: `detections` (JSONB), `chat_messages`, `artifacts` tables.

### Backend endpoints to build
```
POST /auth/signup          {email, password} → 201
POST /auth/login           {email, password} → {access_token}
GET  /projects             → list owned projects
POST /projects             {name} → create empty project
PATCH /projects/{id}       {name} → rename
DELETE /projects/{id}      → delete project + its files on disk
```

Every project query MUST filter by `user_id == current_user.id` — this is your security story ("horizontal authorization enforced at query level").

### Frontend pages
- **Login/Signup:** two forms sharing validation logic; show API errors inline ("email already registered").
- **Auth context:** store token in memory (+ localStorage), axios request interceptor attaches it automatically, response interceptor catches 401 → redirect to login.
- **Dashboard:** grid of project cards (thumbnail, name, colored status chip, scan date) + prominent "New Scan" button opening a create dialog.

### Definition of Done
- Register two users; user A cannot fetch user B's projects (verify with curl/Postman). ✅
- Refreshing the dashboard while logged in keeps you logged in. ✅
- Deleting a project removes its row AND its uploaded files. ✅

---

# PHASE 2 — Video Upload & Async Pipeline Skeleton

**Duration:** mid Week 2 → Week 3
**Plain-language goal:** User picks a phone video → uploads with a progress bar → server runs a multi-step background job whose live status shows on screen. Still zero AI — we're building the conveyor belt before putting machines on it.

### Concept: why asynchronous? (viva favorite)
Video processing takes minutes. HTTP requests must respond in seconds or they time out. So upload returns immediately; heavy work runs in a **background task**; frontend polls `GET /projects/{id}/status` every 3 seconds. This mirrors how real systems use Celery/queues — we use FastAPI `BackgroundTasks` because single-user demo scale doesn't justify Redis infrastructure. Say exactly that trade-off in viva.

### Upload mechanics
- Frontend: `<input accept="video/*" capture="environment">` — on phones this opens the camera directly.
- Axios upload with `onUploadProgress` callback → bind percentage to a progress bar component.
- Backend streams multipart body to `storage/uploads/{project_id}/video.mp4` (stream, don't load 500MB into RAM).
- Validate extension ∈ {.mp4, .mov, .webm} and size ≤ 500MB before saving.

### Pipeline state machine (this becomes a beautiful sequence diagram in your report)
```
UPLOADED ─► EXTRACTING ─► TRAINING_3D ─► DETECTING ─► DONE
    └────────── any stage throws ──────────┴─► FAILED (error_message saved)
```
Each stage wrapped in try/except; on failure write human-readable reason into `error_message` so the UI can display "Training failed: scene too dark" instead of spinning forever.

### Stage 1 — Frame extraction (FFmpeg)
```bash
ffmpeg -i video.mp4 -vf "scale=-2:720,fps=4" frames/frame_%05d.jpg
```
Why 720p @ 4fps: splat training doesn't need motion smoothness, it needs sharp overlapping photos. 60s video → ~240 frames ≈ ideal for a 6GB GPU. Blurrier but lighter than 1080p = fewer VRAM crashes.

### Status polling UI
Timeline component showing stages as steps with spinner ✓/✗ states. Poll stops when DONE/FAILED.

### Definition of Done
- Upload a 45s phone video → watch EXTRACTING → see ~180 frame files appear. ✅
- Feed a corrupt file → project lands in FAILED with message, UI shows it. ✅
- Killing the server mid-processing doesn't leave status stuck at TRAINING forever (stale jobs reset to FAILED on startup check). ✅

---

# PHASE 3 — 3D Reconstruction (Highest-Risk Phase)

**Duration:** Week 3 → Week 4 (⚠️ start Postshot experiments in Week 1 evenings — do not wait)
**Plain-language goal:** Turn ~200 photos into a navigable 3D model of the room using gaussian splatting.

### Concept: what is gaussian splatting? (guaranteed viva question)
Classical photogrammetry builds meshes (triangles) — slow, brittle on shiny/transparent surfaces. **Gaussian splatting** (SIGGRAPH 2023) represents the scene as millions of soft colored ellipsoids ("gaussians") trained by gradient descent until their rendering matches every input photo. Result: photorealistic, renderable in real-time in the browser, robust to real-world messiness. That's why the field switched.

### Path A — Postshot (recommended)
1. New job → import frame folder → it runs SfM (structure-from-motion = figures out camera positions).
2. Train ~15–30 min on RTX 2060; watch PSNR climb.
3. Export as **`.ply` (splat format)** or `.splat`.
4. Your code's job: automate invocation/watching — `services/reconstruct.py` monitors the export folder, moves finished artifact to `storage/splats/{project_id}.ply`, updates DB status.

### Path B — nerfstudio + gsplat (fallback, fully scripted)
`ns-process-data` (COLMAP poses) → `ns-train splatfacto` → export .ply. Harder to install on Windows; use WSL2 or native build. Choose only if you want the "everything scripted" story or Path A fails.

### Capture quality rules (put these tips IN your upload UI — evaluators notice)
- Walk slowly in a loop around the room's perimeter, then cross the middle
- Keep lighting even; avoid pointing at bare windows
- 30–60 seconds is plenty; more ≠ better on 6GB VRAM
- Textured rooms reconstruct far better than blank walls

### Risk management (do this week 1, not week 3)
- Train 3 scenes immediately: a bedroom, the target demo room, a corridor. Archive exports.
- If local training proves unreliable: export from the Luma AI phone app for demo data; your pipeline code stays identical — swap the trainer later. Honest fallback, zero scope change.

### Preview image generation
Pick the sharpest extracted frame (variance-of-Laplacian blur score via OpenCV) as the dashboard thumbnail. Cheap, effective, one function.

### Definition of Done
- One fully automated run: upload video → statuses advance → `.ply` exists on disk linked to the project record. ✅
- 3 archived demo splats safely copied outside the repo. ✅

---

# PHASE 4 — Interactive 3D Viewer

**Duration:** Week 4
**Plain-language goal:** Render the trained splat in the browser with rotate/zoom/fullscreen, loading fast enough to demo without embarrassment.

### Implementation
- `@mkkellogg/gaussian-splats-3d` plugs into Three.js; wrap it in a React component mounted via `@react-three/fiber`.
- Serve `storage/splats/` through FastAPI `StaticFiles` mount (enable range requests for progressive loading).
- Lazy-load the viewer chunk (`React.lazy`) so the 1MB+ Three.js bundle doesn't slow the login page.
- Controls preset: orbit + zoom limits (don't let users fly inside the floor), double-click to recenter.
- Loading overlay with % progress; error card with "Re-process" button if artifact missing.
- Test on an actual phone browser — touch orbit + pinch zoom must work; this is your "mobile responsive" claim made tangible.

### Performance expectations (be honest in report)
Desktop Chrome: 50–60 fps typical scenes. Mid-range phones: 25–40 fps. Cap device pixel ratio at 1.5 to avoid mobile thermal throttling.

### Definition of Done
Demo splat loads <10s on normal Wi-Fi, orbits smoothly, fullscreen toggles, degrades gracefully on missing file. ✅

---

# PHASE 5 — AI Object Detection & Analytics

**Duration:** Week 5
**Plain-language goal:** Look through the extracted frames, find furniture, count it, locate it — producing the single most important file in the project: `objects.json`.

### Detection pipeline
1. Load `yolov8n.pt` once (nano = fast, accurate enough, fits easily in 6GB alongside everything).
2. Run inference on every Nth frame (every 2nd is plenty) → bounding boxes + classes + confidences.
3. **Cross-frame dedup** (your own heuristic): same class boxes whose projected positions are within threshold distance across consecutive frames = same physical object → keep highest-confidence sighting. Without this, one chair counted 40 times.
4. Aggregate into canonical structure:

```json
{
  "project_id": "...",
  "calibration": null,
  "detections": [
    {"class": "chair",  "count": 12, "positions": [{"x": 2.1, "z": -0.4, "confidence": 0.91}]},
    {"class": "dining table", "count": 3, "positions": [...]},
    {"class": "couch",  "count": 1, "positions": [...]}
  ],
  "meta": {"frames_processed": 110, "video_duration_s": 48}
}
```

Store as JSONB in a `detections` table (one row per project, versioned on re-process).

### ⚠️ Honest limitation (address proactively in report + viva)
COCO-pretrained YOLO detects: chairs, dining tables, couches, beds, TVs, potted plants, refrigerators, sinks. It does **NOT** reliably detect doors, windows, counters. Options: demo with supported classes + state limitation openly (fine), OR fine-tune on a small custom dataset (~150 annotated images, Roboflow free tier, one evening — strong bonus points), OR Grounding DINO open-vocabulary as stretch goal. Never claim undetected classes work.

### Analytics computed FROM objects.json
| Metric | Formula |
|---|---|
| Furniture count | Σ counts across furniture classes |
| Seating capacity (raw) | chairs + couches×3 |
| Room count | from Phase 6 DBSCAN (placeholder 1 until then) |
| Area estimate | from calibrated bounds (Phase 6) |
| Empty space % | floor area minus footprint estimates |
| Scan date | straight from project row |

Frontend: recharts cards — bar chart of counts, pie of category share, big-number KPI tiles.

### Definition of Done
Hand-count chairs in 10 sampled frames vs system count: within ±1. ✅ Analytics tab populated for a DONE project. ✅

---

# PHASE 6 — Original Algorithms (Your MCA Differentiator)

**Duration:** Week 6
**Plain-language goal:** Write the three modules that are *yours*, not a library's. These answer the examiner question "what did YOU actually build?"

### Module A — Measurement Calibration (units → meters)
**Problem:** splat coordinates are arbitrary units; "the room is 14 wide" means nothing.
**Method:** a standard chair seat is ≈0.45 m tall. From detected chair bounding-box heights across frames, compute median pixel height → ratio gives meters-per-pixel at typical depth → propagate through splat world scale. Output `meters_per_unit` written back into `objects.json.calibration`.
**Report value:** converts "estimates" into "calibrated estimates" — defensible language.

### Module B — Room Segmentation (DBSCAN clustering)
**Input:** calibrated XZ positions of all detected objects.
**Method:** sklearn DBSCAN groups objects that lie close on the floor plane into clusters; each cluster ≈ a room zone. Tune `eps` via k-distance plot (include the plot in your report — examiners love methodology evidence). Objects labeled noise (-1) = corridors/unassigned.
**Output:** room assignments R1…Rn, enabling "which room has the most free space?"

### Module C — Seating Capacity Estimator
Deterministic, explainable rules:
```
capacity = chairs
         + stools
         + couches × 3
         capped_at (dining_tables × 4 + counters × 2)   # seats need surfaces
```
Document each rule's rationale — this is the function you walk through line-by-line if asked.

### Floor Plan Renderer (frontend canvas)
- Top-down plot: dot per object, color-coded by class (legend included)
- DBSCAN cluster hulls drawn as room boundaries with labels R1, R2…
- Calibrated dimension annotations along bounding box edges + scale bar ("← 1 m →")
- Empty-space shading (light gradient away from object clusters)

Every element above traces to a PRD requirement — say that mapping explicitly in the report.

### Definition of Done
All three modules have pytest unit tests with synthetic inputs (fake positions → expected clusters/capacity). ✅ Floor plan tab renders a real project end-to-end. ✅

---

# PHASE 7 — AI Assistant & Weight Features

**Duration:** Week 6 → mid Week 7
**Plain-language goal:** Let users converse with their twin, plus ship the four features that elevate the demo.

### Chat architecture
```
User question ─► POST /projects/{id}/ask
                  │ prompt = compacted objects.json summary
                  │        + analytics metrics
                  │        + conversation history (last 6 turns)
                  ▼
             Gemini Flash (free tier) ─► grounded answer ─► saved to chat_messages
```
Prompt template instructs the model: *"Answer ONLY from the provided JSON. If unknown, say so."* — prevents hallucinated chair counts, which is your accuracy guarantee. Show this template in the report.

Suggested-question chips on empty chat state: "How many chairs are present?" · "Which room has the most free space?" · "Estimate seating capacity" · "Suggest better furniture placement."

### Weight features (build in this order)
1. 🎤 **Voice input** — Web Speech API (`webkitSpeechRecognition`), browser-native, ~2 hours, biggest live-demo wow.
2. 🔥 **Heatmap toggle** — canvas overlay interpolating object density; instantly visualizes "free space."
3. 📄 **PDF report** — jsPDF: cover page, project meta, KPI table, object-count table, floor-plan canvas snapshot via `.toDataURL()`. Evaluators keep PDFs; nobody revisits live apps.
4. 🐳 **Docker Compose** — backend + frontend services, one `docker compose up`. Half a day, earns "deployment-ready" line.

### Definition of Done
Spoken "how many chairs?" → correct spoken-context answer in <5 s on demo scene. ✅ PDF downloads matching on-screen numbers. ✅ Fresh clone boots with one command. ✅

---

# PHASE 8 — Hardening, Testing & Polish

**Duration:** Week 7
**Plain-language goal:** Turn "works on my machine" into "defensible under scrutiny."

### Testing matrix (fills the mandatory test-case table in your report)
| Layer | Tool | Cases |
|---|---|---|
| Unit | pytest | bcrypt roundtrip, JWT expiry, calibration math, DBSCAN on synthetic points, capacity rules |
| Integration | pytest + httpx TestClient | signup→login→create→upload(mock)→fetch flow |
| Manual UAT | checklist | full journey on desktop Chrome + Android Chrome |
| Security spot-checks | manual | other-user's project id → 404; oversized upload → 413; bad token → 401 |

Aim ~25–35 passing tests. More isn't better; documented coverage is.

### Hardening checklist
- Rate-limit `/auth/*` (slowapi) — mention "brute-force mitigation"
- Upload MIME sniffing beyond extension trust
- Global exception handler → JSON errors, no stack traces leaked
- Every page has empty/loading/error states (screenshot-worthy UX polish)
- Mobile pass: dashboard grid collapses, viewer touch controls, chat keyboard overlap fix

### Definition of Done
Clean-machine runthrough: fresh user → upload → wait → view twin → ask voice question → export PDF, **zero console errors**, test suite green. ✅

---

# PHASE 9 — Documentation & Submission Package

**Duration:** Week 8
**Plain-language goal:** Produce the paper trail that MCA evaluation actually grades, and bulletproof the live demo.

### Report artifacts (start drafting diagrams NOW-ish, finalize here)
- **SRS:** functional (trace each to a module) + non-functional (perf targets from Phases 4/8)
- **Diagrams:** DFD L0/L1/L2 · ER diagram (from Phase 1 schema) · UML use-case, class, sequence (upload→pipeline is your showcase sequence diagram) · architecture diagram (top of this file)
- **Data dictionary** for every table/column
- **Algorithm chapter:** Modules A/B/C with formulas, k-distance plot, worked numeric example
- **Testing chapter:** filled test-case table + screenshots
- **Limitations section (write it honestly — it protects you):** monocular measurement tolerance ±10–20%, COCO class coverage, single-GPU concurrency ceiling, BackgroundTasks vs Celery trade-off
- **Future scope:** AR measurement, multi-floor, collaboration, VR — lifted verbatim from PRD

### Demo insurance (non-negotiable)
- Pre-train 3 splats archived locally; viva never depends on a 20-minute live training run
- Screen-record a full pipeline run as backup video
- Prepare crisp answers: *"Why splats over meshes/meshroom?"* · *"How accurate are measurements and why?"* · *"What breaks with 100 users?" (BackgroundTasks ceiling → Celery migration path)* · *"What did you personally author?" (Phase 6 modules + dedup heuristic + pipeline orchestrator)*

### Final deliverable checklist
- [ ] Working system (local + docker compose up)
- [ ] GitHub repo: README with screenshots + architecture diagram + setup steps
- [ ] Report PDF (all diagrams, tests, limitations)
- [ ] PPT (12–15 slides) + backup demo video
- [ ] Two successful dry-run presentations completed

---

## Risk Register (glance weekly)

| Risk | Likelihood | Mitigation |
|---|---|---|
| Splat training fails on 6GB VRAM | Medium | Lower res/fps; Path B; Luma-export fallback (Phase 3) |
| YOLO misses key classes | High | Scope claims honestly; optional fine-tune evening |
| Week 3 slips | Medium | Phases 6–7 have buffer; weight features cuttable in order 4→3→2 |
| Laptop failure near deadline | Low | Code on GitHub; splats archived externally since Day 1 week |
