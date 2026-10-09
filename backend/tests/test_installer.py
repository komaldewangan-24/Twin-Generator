"""The Brush installer against a local fake GitHub: dropped connections resume, bad files are rejected."""

import hashlib
import importlib.util
import io
import tarfile
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "install_brush.py"


@pytest.fixture()
def installer(monkeypatch):
    spec = importlib.util.spec_from_file_location("install_brush", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "SOCKET_TIMEOUT_S", 5)
    monkeypatch.setattr(module.time, "sleep", lambda s: None)   # no real waiting between retries (undone after each test)
    return module


def make_archive(name: str) -> bytes:
    """A tiny stand-in for the real release: one 'brush_app' that prints a version."""
    body = b"#!/bin/sh\necho brush-cli 0.0.test\n"
    buf = io.BytesIO()
    if name.endswith(".zip"):
        with zipfile.ZipFile(buf, "w") as z:
            # like the real Windows release: files at the root, no containing folder
            z.writestr("brush_app.exe", body)
            z.writestr("README.md", b"readme")
            z.writestr("LICENSE", b"licence")
            z.writestr("padding.bin", b"\x00" * 200_000, compress_type=zipfile.ZIP_STORED)   # big enough to drop mid-download
    else:
        with tarfile.open(fileobj=buf, mode="w:xz") as t:
            folder = tarfile.TarInfo("brush-app-test")          # real tarballs list the folder itself (no trailing slash)
            folder.type, folder.mode = tarfile.DIRTYPE, 0o755
            t.addfile(folder)
            info = tarfile.TarInfo("brush-app-test/brush_app")
            info.size, info.mode = len(body), 0o755
            t.addfile(info, io.BytesIO(body))
    # tar.xz may carry trailing zeros; a zip must end with its own index, so its padding is inside
    return buf.getvalue() + (b"" if name.endswith(".zip") else b"\x00" * 200_000)


class FakeGitHub:
    def __init__(self, name: str, data: bytes, checksum: str | None = None, drop_first: bool = False):
        self.name, self.data, self.drop_first = name, data, drop_first
        self.checksum = checksum or hashlib.sha256(data).hexdigest()
        self.requests: list[tuple[str, str | None]] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                outer.requests.append((self.path, self.headers.get("Range")))
                if self.path.endswith(".sha256"):
                    body = f"{outer.checksum} *{outer.name}\r\n".encode()
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                start = 0
                rng = self.headers.get("Range")
                if rng:
                    start = int(rng.split("=")[1].split("-")[0])
                chunk = outer.data[start:]
                self.send_response(206 if rng else 200)
                if rng:
                    self.send_header("Content-Range", f"bytes {start}-{len(outer.data) - 1}/{len(outer.data)}")
                self.send_header("Content-Length", str(len(chunk)))
                self.end_headers()
                if outer.drop_first and not rng:
                    self.wfile.write(chunk[: len(chunk) // 2])   # promise everything, deliver half, hang up
                    self.wfile.flush()
                    self.connection.close()
                    return
                self.wfile.write(chunk)

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()


@pytest.fixture()
def github(installer, monkeypatch):
    servers = []

    def start(**kwargs):
        name = installer.asset_name()
        server = FakeGitHub(name, make_archive(name), **kwargs)
        servers.append(server)
        monkeypatch.setenv("TWIN_BRUSH_BASE", server.url)
        return server

    yield start
    for s in servers:
        s.close()


def run(installer, monkeypatch, tmp_path, *extra):
    monkeypatch.setattr("sys.argv", ["install_brush.py", "--dest", str(tmp_path), *extra])
    installer.main()


def test_download_verify_and_install(installer, github, monkeypatch, tmp_path, capsys):
    server = github()
    run(installer, monkeypatch, tmp_path)
    exe = installer.find_exe(tmp_path)
    assert exe is not None and exe.is_file()
    out = capsys.readouterr().out
    assert "Checksum OK" in out
    assert not list(tmp_path.glob("*.part")) and not (tmp_path / installer.asset_name()).exists(), "no leftovers"
    assert any(not path.endswith(".sha256") for path, _ in server.requests)


def test_a_dropped_connection_resumes_instead_of_starting_over(installer, github, monkeypatch, tmp_path, capsys):
    server = github(drop_first=True)
    run(installer, monkeypatch, tmp_path)
    assert installer.find_exe(tmp_path) is not None
    downloads = [rng for path, rng in server.requests if not path.endswith(".sha256")]
    assert downloads[0] is None and downloads[1] and downloads[1].startswith("bytes="), downloads
    assert "interrupted" in capsys.readouterr().out


def test_a_wrong_checksum_is_rejected_and_nothing_is_installed(installer, github, monkeypatch, tmp_path):
    github(checksum="0" * 64)
    with pytest.raises(installer.InstallError, match="checksum"):
        run(installer, monkeypatch, tmp_path)
    assert installer.find_exe(tmp_path) is None
    assert not (tmp_path / installer.asset_name()).exists(), "the bad download must be deleted"


def test_a_file_saved_by_hand_in_the_folder_is_used_without_downloading(installer, github, monkeypatch, tmp_path, capsys):
    server = github()
    (tmp_path / installer.asset_name()).write_bytes(make_archive(installer.asset_name()))
    # the checksum for a different build of the stand-in archive will not match, so serve the matching one
    server.checksum = hashlib.sha256((tmp_path / installer.asset_name()).read_bytes()).hexdigest()
    run(installer, monkeypatch, tmp_path)
    assert installer.find_exe(tmp_path) is not None
    assert "already downloaded" in capsys.readouterr().out
    assert all(path.endswith(".sha256") for path, _ in server.requests), "the archive must not be downloaded again"


def test_file_option_installs_a_downloaded_archive(installer, github, monkeypatch, tmp_path):
    name = installer.asset_name()
    data = make_archive(name)
    elsewhere = tmp_path / "Downloads"
    elsewhere.mkdir()
    (elsewhere / name).write_bytes(data)
    github(checksum=hashlib.sha256(data).hexdigest())
    dest = tmp_path / "tools"
    run(installer, monkeypatch, dest, "--file", str(elsewhere / name))
    assert installer.find_exe(dest) is not None
    assert (elsewhere / name).exists(), "a file the user supplied is never deleted"


def test_a_damaged_archive_gives_a_clear_message(installer, github, monkeypatch, tmp_path):
    name = installer.asset_name()
    bad = b"this is not an archive" * 1000
    github(checksum=hashlib.sha256(bad).hexdigest())
    (tmp_path / name).write_bytes(bad)
    with pytest.raises(installer.InstallError, match="damaged"):
        run(installer, monkeypatch, tmp_path)


def test_checksum_files_with_bom_and_windows_line_endings_are_understood(installer, monkeypatch):
    digest = "ab" * 32

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def read(self):
            return f"﻿{digest} *brush-app-x86_64-pc-windows-msvc.zip\r\n".encode("utf-8")

    monkeypatch.setattr(installer, "open_url", lambda req: Resp())
    assert installer.expected_checksum("brush-app-x86_64-pc-windows-msvc.zip") == digest


def test_a_zip_without_a_top_folder_unpacks_into_its_own_folder(installer, tmp_path):
    """The real Windows zip has brush_app.exe at its root. README and LICENSE must not end up
    loose in backend/tools/."""
    archive = tmp_path / "brush-app-x86_64-pc-windows-msvc.zip"
    archive.write_bytes(make_archive("x.zip"))
    tools = tmp_path / "tools"
    tools.mkdir()
    installer.unpack(archive, tools)
    assert (tools / "brush-app-x86_64-pc-windows-msvc" / "brush_app.exe").is_file()
    assert not (tools / "README.md").exists() and not (tools / "brush_app.exe").exists()
    assert installer.find_exe(tools).name == "brush_app.exe"


def test_an_archive_that_already_has_a_folder_keeps_it(installer, tmp_path):
    archive = tmp_path / "brush-app-aarch64-apple-darwin.tar.xz"
    archive.write_bytes(make_archive("x.tar.xz"))
    installer.unpack(archive, tmp_path / "tools")
    assert (tmp_path / "tools" / "brush-app-test" / "brush_app").is_file()
