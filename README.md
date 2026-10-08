# AI Digital Twin Generator

Turn a short smartphone walkthrough video into an interactive digital twin: object detection, room segmentation, floor plans, seating analytics, PDF reports, an AI assistant, and a Gaussian Splat 3D viewer.

Built as an MCA major project. The web app runs entirely on CPU -- no NVIDIA GPU is required for the detection pipeline.

---

## Features

- **Authentication** -- JWT signup/login, bcrypt password hashing, project ownership enforced on every endpoint.
- **Video processing pipeline** (runs async after upload):
  1. FFmpeg extracts frames
  2. COLMAP (via `pycolmap`) recovers the camera path and a sparse 3D point cloud
  3. YOLOv8 (ONNX Runtime, CPU) detects objects; each sighting is placed on the floor in 3D and merged across frames, so counts and positions are real
  4. Room size, floor area, ceiling height and free floor space are estimated from the reconstruction
  5. Brush trains a photorealistic Gaussian splat of the room on the GPU (Metal on Mac, Vulkan/DX12 elsewhere), shown in the browser viewer
  6. If camera positions cannot be recovered the app falls back to 2D mode and says why
- **Interactive results** -- object inventory, 2D floor plan + heatmap, analytics dashboard, live status timeline.
- **PDF report export** (jsPDF) of the project results.
- **AI assistant** -- ask natural-language questions about the scanned space ("how big is the room?", "where is the TV?", "suggest a layout"). Answers can point at objects in the 3D model. Works offline with built-in rules, or with Gemini, Claude or a free local model (Ollama).
- **Gaussian Splat viewer** -- attach a trained `.ply` / `.splat` and explore the space in 3D in the browser (three.js + `@mkkellogg/gaussian-splats-3d`).
- **Multi-user workspace** -- one dashboard, many projects, per-project progress.

---

## Architecture

```
Browser (React + Vite)
   |  JWT Bearer
   v
FastAPI REST API
   |-- auth / projects / uploads / detections / chat
   |
   +--> Background pipeline (per upload)
   |      ffmpeg -> frames -> COLMAP camera path -> YOLOv8 (ONNX) detections
   |      -> objects placed on the floor in 3D, merged across frames
   |      -> zones (DBSCAN), room size, capacity, free space
   |      -> Brush trains the Gaussian splat (GPU) -> viewer
   |
   +--> SQLite (dev) / PostgreSQL (prod)
```

Uploads, extracted frames, previews and splats live under `backend/storage/` and are git-ignored. Files are served only through signed, expiring links.

---

## Tech stack

| Layer     | Choice |
|-----------|--------|
| Backend   | FastAPI, SQLAlchemy 2, Uvicorn, python-jose (JWT), passlib/bcrypt |
| Detection | YOLOv8n, ONNX Runtime (CPU), OpenCV, scikit-learn (DBSCAN) |
| 3D        | pycolmap (COLMAP) for camera poses, Brush for Gaussian splat training |
| Media     | FFmpeg (frame extraction; bundled via imageio-ffmpeg) |
| AI chat   | Gemini / Claude / any OpenAI-compatible server incl. Ollama (optional) + rule-based fallback |
| Frontend  | React 19, Vite, Tailwind CSS 4, Zustand, React Router 7 |
| UI / data | Recharts, jsPDF, three.js, `@mkkellogg/gaussian-splats-3d` |
| Tests     | pytest + FastAPI TestClient |

---

## Prerequisites

- **Python 3.11+** (developed and tested on 3.13)
- **Node.js 20.19+ or 22.12+** (required by Vite 8; developed on 22)
- **FFmpeg** available on your `PATH`
  - Windows: `winget install Gyan.FFmpeg`
  - macOS: `brew install ffmpeg`
  - Linux: `sudo apt install ffmpeg`

  The backend also auto-discovers common WinGet install locations if `ffmpeg` is not on `PATH`.

---

## Getting started

### 1. Backend

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

**Model weights.** The detector needs `backend/models/yolov8s.onnx` (or `yolov8n.onnx`). Model files are intentionally not committed to this repository, so export it once. `ultralytics` is deliberately not in `requirements.txt` (it pulls in torch and pins `numpy<2` on macOS), so use a throwaway environment:

```bash
python -m venv /tmp/export-venv && source /tmp/export-venv/bin/activate
pip install ultralytics onnx
yolo export model=yolov8s.pt format=onnx      # or yolov8n.pt for a smaller, less accurate model
mkdir -p backend/models && cp yolov8s.onnx backend/models/
```

The API then runs on ONNX Runtime (CPU), which is the tested path. If you do install `ultralytics` into the main environment, `detector.py` will use it instead.

**FFmpeg** must be on your `PATH`, or set `FFMPEG_PATH` to the binary.

**Configure environment:**

```bash
cp .env.example .env
```

`DATABASE_URL` is optional: leaving it empty creates a local SQLite database at `backend/storage/database.db`. Set `JWT_SECRET_KEY` to a long random value (`openssl rand -hex 32`); if it is left empty the app falls back to an insecure development key.

**Run:**

```bash
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

App: http://localhost:5173

The frontend calls the API at `http://localhost:8000` by default. Set `VITE_API_URL` (for example in `frontend/.env.local`) to point it elsewhere.

---

## Tests

```bash
cd backend
python -m pytest tests/ -q
```

Tests run against an isolated temporary SQLite database (configured in `tests/conftest.py`), so they never touch your development database and can run while the dev server is up.

---

## API overview

All project endpoints require `Authorization: Bearer <token>`.

| Method | Path                              | Purpose |
|--------|-----------------------------------|---------|
| POST   | `/auth/signup`                    | Create account, returns token |
| POST   | `/auth/login`                     | Sign in, returns token |
| GET    | `/projects`                       | List own projects |
| POST   | `/projects`                       | Create project |
| GET    | `/projects/{id}`                  | Project detail |
| PATCH  | `/projects/{id}`                  | Rename / update |
| DELETE | `/projects/{id}`                  | Delete project and its files |
| POST   | `/projects/{id}/upload`           | Upload walkthrough video (multipart field `file`) |
| GET    | `/projects/{id}/status`           | Pipeline status + stage timeline |
| GET    | `/projects/{id}/objects`          | Detected objects, counts, positions |
| GET    | `/projects/{id}/analytics`        | Rooms, capacity, area (optional `?room_width_m=`) |
| POST   | `/projects/{id}/ask`              | Ask a question about the space |
| POST   | `/projects/{id}/splat`            | Attach a trained splat file (field `file`) |
| POST   | `/projects/{id}/splat/demo`       | Attach `storage/splats/demo.splat` if you provide one |
| POST   | `/files/token`                    | Short-lived token for `/files/{id}/preview.jpg` and `/files/{id}/model.ply` |

Health check: `GET /health`

---

## The assistant

Out of the box the assistant uses built-in rules (counts, capacity, room size, free space, "where is the TV?", layout ideas). For free-form questions, pick a language model in `backend/.env`:

```bash
LLM_PROVIDER=ollama        # free, runs on your computer (install from ollama.com, then `ollama pull llama3.2`)
LLM_MODEL=llama3.2

# or a hosted model:
LLM_PROVIDER=gemini        # or: anthropic
LLM_API_KEY=your-key
```

The model only ever sees the scan's structured data (object counts and positions, zones, room size), never the video. The app deliberately ignores generic keys such as `ANTHROPIC_API_KEY` in your shell: only `LLM_PROVIDER` and `LLM_API_KEY` in `.env` choose where your data goes.

---

## Real 3D models

Each upload builds its own Gaussian splat. This needs two things beyond `pip install`:

1. `pycolmap` (already in `requirements.txt`): camera positions. Runs on CPU, about 3 minutes for 200 frames.
2. **Brush**, the splat trainer. Download the release for your OS from <https://github.com/ArthurBrussee/brush/releases> and unpack it under `backend/tools/` (for example `backend/tools/brush-app-aarch64-apple-darwin/brush_app`). The app finds it there, or set `BRUSH_PATH`. Brush needs a GPU with Metal, Vulkan or DX12 but **not** NVIDIA.

Expect about 10 to 20 minutes of training on an Apple M-series chip. Objects, floor plan and analytics are available as soon as the camera path is found; the 3D tab shows progress until the model is ready.

For a good model: walk slowly in a loop around the room's edge, keep lighting even, avoid blank walls and pointing at windows, and film 30 to 60 seconds. If fewer than about a third of the frames can be placed in 3D, the app tells you and keeps the 2D results.

**Scale is an estimate.** Structure-from-motion has no absolute scale, so sizes assume the phone was held at 1.4 m (cross-checked against a typical 2.5 m ceiling). Enter a tape-measured side on the Analytics tab to correct it. `scripts/evaluate.py` compares a scan against your measurements and hand counts.

You can still attach a splat trained elsewhere (Luma, Polycam, KIRI Engine) on the 3D tab for older scans.

**Interacting with the model:** orbit, zoom and fullscreen; **Walkthrough** replays the path you filmed; labels float on detected objects; "Show in 3D" in the Objects tab, the floor plan and the assistant flies to an object.

**Viewer note:** cross-origin isolation headers (`COOP`/`COEP`) are not enabled in the dev server, so the viewer sets `sharedMemoryForWorkers: false`. Without that, the splat sort worker silently fails and the canvas stays blank.

### Doors, windows and lights (optional)

The COCO model does not know them. `scripts/export_open_vocab.py` exports an open-vocabulary YOLO-World model to ONNX (about 370 MB of one-time downloads; AGPL/GPL licence). If `backend/models/open_vocab.onnx` exists the app uses it automatically.

---

## Project structure

```
backend/
  app/
    api/          auth, projects, uploads, detections, chat routers
    core/         config, database, security
    models/       SQLAlchemy models
    schemas/      Pydantic schemas
    services/     pipeline, detector, extractor, analytics, capacity,
                  segment_rooms, calibrate, preview, chat, storage
  models/         YOLOv8n ONNX weights (git-ignored)
  storage/        uploads, frames, splats, database (git-ignored)
  tests/          pytest suite + isolated test DB config
frontend/
  src/
    components/   SplatViewer, FloorPlan, StatusTimeline, ChatPanel, ...
    pages/        Login, Signup, Dashboard, ProjectDetail
    stores/       Zustand auth store
    lib/          axios client
```

---

## Known limitations

- **Sizes are estimates** (see "Scale is an estimate"). Typical error is tens of percent until corrected with a measurement.
- **Counts can be wrong** when objects are hidden, look alike, or the video is blurry. An object must be seen in at least 2 frames to count.
- **CPU detection and training time.** Longer videos take proportionally longer.
- **Not detected without the optional model:** doors, windows, counters and lights.
- **Development storage.** Files are on local disk, served through short-lived signed links (`/files/...`). Use object storage and PostgreSQL for deployment.
- **`backend/requirements-core.txt`** is a Phase-1 subset (auth/CRUD only). Use `backend/requirements.txt` for the full app.

---

## License

No license file has been added yet. All rights reserved by default -- add a `LICENSE` before publishing publicly if you intend to allow reuse.
