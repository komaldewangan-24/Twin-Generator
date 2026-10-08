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
