# AI Digital Twin Generator

Turn a short smartphone walkthrough video into an interactive digital twin: object detection, room segmentation, floor plans, seating analytics, PDF reports, an AI assistant, and a Gaussian Splat 3D viewer.

Built as an MCA major project. The web app runs entirely on CPU -- no NVIDIA GPU is required for the detection pipeline.

---

## Features

- **Authentication** -- JWT signup/login, bcrypt password hashing, project ownership enforced on every endpoint.
- **Video processing pipeline** (runs async after upload):
  1. FFmpeg extracts frames from the walkthrough video
  2. YOLOv8 (ONNX Runtime, CPU) detects furniture and objects per frame
  3. DBSCAN clusters object floor positions into room zones
  4. Calibration estimates real-world scale and area
  5. Seating-capacity rules produce deterministic capacity numbers
- **Interactive results** -- object inventory, 2D floor plan + heatmap, analytics dashboard, live status timeline.
- **PDF report export** (jsPDF) of the project results.
- **AI chat** -- ask natural-language questions about the scanned space. Uses Google Gemini when a key is configured, with a built-in rule-based fallback that needs no API key.
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
   |      ffmpeg  ->  frames  ->  YOLOv8 (ONNX)  ->  detections.json
   |      ->  DBSCAN rooms  ->  calibration  ->  capacity/analytics
   |
   +--> SQLite (dev) / PostgreSQL (prod)
```

Uploads, extracted frames, previews and splats live under `backend/storage/` and are git-ignored.

---

## Tech stack

| Layer     | Choice |
|-----------|--------|
| Backend   | FastAPI, SQLAlchemy 2, Uvicorn, python-jose (JWT), passlib/bcrypt |
| Detection | YOLOv8n, ONNX Runtime (CPU), OpenCV, scikit-learn (DBSCAN) |
| Media     | FFmpeg (frame extraction) |
| AI chat   | Google Gemini (optional) + rule-based fallback |
| Frontend  | React 19, Vite, Tailwind CSS 4, Zustand, React Router 7 |
| UI / data | Recharts, jsPDF, three.js, `@mkkellogg/gaussian-splats-3d` |
| Tests     | pytest + FastAPI TestClient |

---

## Prerequisites

- **Python 3.11+** (developed and tested on 3.13)
- **Node.js 18+** (developed on 22)
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

**Model weights.** The detector needs `backend/models/yolov8n.onnx`. Model files are intentionally not committed to this repository. Either export it yourself:

```bash
yolo export model=yolov8n.pt format=onnx
```

or download the official YOLOv8n ONNX asset from the Releases page of the `ultralytics/ultralytics` GitHub repository, then place it at `backend/models/yolov8n.onnx`.

If PyTorch is unavailable on your machine (the default `torch` build is unreliable on some Windows hosts), the API still works: `detector.py` automatically falls back to ONNX Runtime, which is the tested path.

**Configure environment:**

```bash
cp .env.example .env
```

All values are optional for local development -- leaving `DATABASE_URL` empty creates a local SQLite database at `backend/storage/database.db`.

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

The frontend calls the API at `http://localhost:8000` (see `frontend/src/lib/api.js`).

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
| POST   | `/projects/{id}/splat/demo`       | Attach the bundled demo splat |

Health check: `GET /health`

---

## 3D Gaussian Splat workflow

Training a Gaussian Splat from video needs a GPU, so it is deliberately **not** part of the server pipeline. The supported flow is:

1. Export frames or the source video from a project.
2. Train a splat outside the app -- Google Colab, Luma AI, or any splatting tool.
3. Upload the exported `.ply` / `.splat` on the project page.

The viewer also ships a demo attachment button for trying the 3D UI without training anything; it requires a splat file to be present at `backend/storage/splats/demo.splat` (git-ignored, so provide your own after cloning).

**Viewer note:** cross-origin isolation headers (`COOP`/`COEP`) are not enabled in the dev server, so the viewer sets `sharedMemoryForWorkers: false`. Without that, the splat sort worker silently fails and the canvas stays blank.

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

- **3D training is external.** The app renders splats; it does not train them (see workflow above).
- **CPU detection.** ONNX Runtime on CPU is accurate but not real time; longer videos take proportionally longer.
- **Scale estimates are approximate.** Room area and capacity are derived heuristically from a single camera view unless you supply a known room width for calibration.
- **Development storage.** Files are stored on local disk; switch to object storage and PostgreSQL for deployment.
- **`backend/requirements-core.txt`** is a Phase-1 subset (auth/CRUD only). Use `backend/requirements.txt` for the full app.

---

## License

No license file has been added yet. All rights reserved by default -- add a `LICENSE` before publishing publicly if you intend to allow reuse.
