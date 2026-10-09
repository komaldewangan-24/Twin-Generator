# Demo scan

This folder makes the **Demo scan** button on the dashboard work on any computer,
with no GPU, no trainer and no video:

| File | What it is |
|---|---|
| `demo.splat` | The 3D model (a Gaussian splat), about a few MB |
| `demo.json` | Objects, room size, floor outline and camera path for that model |
| `preview.jpg` | Thumbnail for the dashboard |
| `gpu_test/` | A tiny training set (16 small photos) used by `python scripts/doctor.py --gpu-test` to check that the graphics card can train 3D models |

## Where the sample comes from

The photos are the **"playroom" scene of the Deep Blending dataset** (Hedman et al.,
"Deep Blending for Free-Viewpoint Image-Based Rendering", SIGGRAPH Asia 2018), as
distributed by the authors of 3D Gaussian Splatting
(<https://github.com/graphdeco-inria/gaussian-splatting>). It was turned into a video, then
processed by this app's own pipeline (COLMAP camera path, Brush training, object placement).

That dataset is published for research use. For a project report or presentation this is
fine to show, with this credit. If you need something you fully own, replace it with your own scan:

```bash
python backend/scripts/export_demo.py <project-id> "Demo: My room"
```

and commit this folder.
