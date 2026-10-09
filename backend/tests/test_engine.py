"""3D engine pieces that need no database: frame extraction and splat conversion."""


def test_ply_to_splat_converts_and_drops_floaters(tmp_path):
    """The converter must keep solid splats, drop near-invisible ones, and
    produce 32 bytes per splat in the layout the web viewer expects."""
    import numpy as np

    from app.services.splat_convert import ply_to_splat

    n = 1000
    fields = ["x", "y", "z", "f_dc_0", "f_dc_1", "f_dc_2", "opacity", "scale_0", "scale_1", "scale_2", "rot_0", "rot_1", "rot_2", "rot_3"]
    data = np.zeros(n, dtype=[(f, "<f4") for f in fields])
    rng = np.random.default_rng(0)
    data["x"], data["y"], data["z"] = rng.normal(0, 1, (3, n))
    data["opacity"] = np.where(np.arange(n) < 800, 3.0, -6.0)   # 800 solid (sigmoid~0.95), 200 near-invisible (~0.002)
    data["scale_0"] = data["scale_1"] = data["scale_2"] = np.log(0.05)
    data["rot_0"] = 1.0

    ply = tmp_path / "in.ply"
    with open(ply, "wb") as f:
        header = "ply\nformat binary_little_endian 1.0\nelement vertex %d\n" % n
        header += "".join(f"property float {name}\n" for name in fields) + "end_header\n"
        f.write(header.encode())
        data.tofile(f)

    out = tmp_path / "out.splat"
    stats = ply_to_splat(ply, out)
    assert 700 <= stats["out"] <= 800        # the 200 invisible ones (and a few outliers) are gone
    assert out.stat().st_size == stats["out"] * 32
    assert out.stat().st_size < ply.stat().st_size


def test_extractor_keeps_short_side_720_for_portrait_and_landscape(tmp_path):
    """Phone video is usually portrait. It must keep full resolution (720 wide),
    not shrink to 405 px wide."""
    import cv2
    import numpy as np

    from app.services.extractor import extract_frames

    for name, (w, h) in {"portrait": (360, 640), "landscape": (640, 360)}.items():
        video = tmp_path / f"{name}.mp4"
        writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"mp4v"), 8, (w, h))
        for i in range(16):
            writer.write(np.full((h, w, 3), 40 + i * 5, np.uint8))
        writer.release()
        out = tmp_path / f"frames_{name}"
        assert extract_frames(str(video), str(out)) > 0
        frame = cv2.imread(str(next(out.glob("*.jpg"))))
        assert min(frame.shape[:2]) == 720, f"{name}: {frame.shape}"
        assert (frame.shape[0] > frame.shape[1]) == (name == "portrait")


def _fake_brush(tmp_path, body: str):
    """A stand-in trainer: a small Python script that behaves like Brush's command line."""
    script = tmp_path / "brush_app"
    script.write_text("#!/usr/bin/env python3\nimport sys, pathlib\nargs = sys.argv\n" + body)
    script.chmod(0o755)
    return str(script)


FAKE_OK = '''
export = pathlib.Path(args[args.index("--export-path") + 1])
splats = int(args[args.index("--max-splats") + 1])
(export / "export_00100.ply").write_text(f"model with at most {splats} splats")
'''


def test_trainer_is_found_even_in_a_nested_windows_style_folder(tmp_path, monkeypatch):
    from app.services import reconstruct

    nested = tmp_path / "tools" / "brush-app-x86_64-pc-windows-msvc" / "brush-app-x86_64-pc-windows-msvc"
    nested.mkdir(parents=True)
    exe = nested / "brush_app.exe"
    exe.write_text("x")
    exe.chmod(0o755)
    (tmp_path / "tools" / "brush-app-x86_64-pc-windows-msvc.zip").write_text("not an exe")
    monkeypatch.setattr(reconstruct, "BASE_DIR", tmp_path)
    monkeypatch.delenv("BRUSH_PATH", raising=False)
    assert reconstruct.find_brush() == str(exe)


def test_trainer_retries_with_lower_memory_settings_when_the_gpu_runs_out(tmp_path, monkeypatch):
    """A 4 GB laptop GPU crashes on the first attempt; the retry must use far lighter settings."""
    from app.services import reconstruct

    brush = _fake_brush(tmp_path, '''
splats = int(args[args.index("--max-splats") + 1])
if splats > 500_000:
    sys.stderr.write("wgpu error: Out of memory while allocating buffer\\n")
    sys.exit(101)
''' + FAKE_OK)
    monkeypatch.setattr(reconstruct, "find_brush", lambda: brush)
    dataset = tmp_path / "ds"
    dataset.mkdir()
    seen = []
    out = reconstruct.train_splat(dataset, tmp_path / "out" / "m.ply", lambda *a: seen.append(a[2]), steps=12000, max_resolution=1280, max_splats=1_000_000)
    assert "at most 300000 splats" in out.read_text()
    assert any("lower graphics-memory" in m for m in seen)


def test_trainer_always_trains_without_view_dependent_colour(tmp_path, monkeypatch):
    from app.services import reconstruct

    brush = _fake_brush(tmp_path, '''
assert args[args.index("--sh-degree") + 1] == "0"
''' + FAKE_OK)
    monkeypatch.setattr(reconstruct, "find_brush", lambda: brush)
    (tmp_path / "ds").mkdir()
    reconstruct.train_splat(tmp_path / "ds", tmp_path / "o" / "m.ply", lambda *a: None)


def test_trainer_failure_messages_tell_people_what_to_do():
    from app.services.reconstruct import explain_trainer_failure

    assert "ran out of memory" in explain_trainer_failure(101, "Out of memory")
    assert "SPLAT_MAX_SPLATS" in explain_trainer_failure(101, "device lost")
    assert "Visual C++" in explain_trainer_failure(3221225781, "")
    assert "graphics adapter" in explain_trainer_failure(101, "No suitable adapter found")
    assert "stopped unexpectedly" in explain_trainer_failure(2, "something odd")


def test_missing_trainer_says_where_to_get_it(tmp_path, monkeypatch):
    import pytest

    from app.services import reconstruct

    monkeypatch.setattr(reconstruct, "find_brush", lambda: None)
    with pytest.raises(reconstruct.ReconstructionError, match="github.com/ArthurBrussee/brush"):
        reconstruct.train_splat(tmp_path, tmp_path / "m.ply", lambda *a: None)


def test_ply_to_splat_caps_the_number_of_splats_keeping_the_most_important(tmp_path):
    import numpy as np

    from app.services.splat_convert import ply_to_splat

    n = 500
    fields = ["x", "y", "z", "f_dc_0", "f_dc_1", "f_dc_2", "opacity", "scale_0", "scale_1", "scale_2", "rot_0", "rot_1", "rot_2", "rot_3"]
    data = np.zeros(n, dtype=[(f, "<f4") for f in fields])
    data["x"] = np.linspace(-1, 1, n)
    data["opacity"] = 3.0
    data["scale_0"] = data["scale_1"] = data["scale_2"] = np.log(np.linspace(0.01, 0.1, n))   # bigger index = bigger splat
    data["rot_0"] = 1.0
    ply = tmp_path / "in.ply"
    with open(ply, "wb") as f:
        f.write(("ply\nformat binary_little_endian 1.0\nelement vertex %d\n" % n + "".join(f"property float {k}\n" for k in fields) + "end_header\n").encode())
        data.tofile(f)
    stats = ply_to_splat(ply, tmp_path / "o.splat", max_count=100)
    assert stats["out"] == 100
    kept = np.fromfile(tmp_path / "o.splat", dtype=[("p", "<f4", 3), ("s", "<f4", 3), ("c", "u1", 4), ("r", "u1", 4)])
    assert kept["s"].max(axis=1).min() > 0.05, "the largest, most important splats must be the ones kept"
