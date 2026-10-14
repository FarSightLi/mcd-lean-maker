import io
import urllib.error

import build_web
from build_web import download_images, image_filename

URL = "https://menu-img.mcd.cn/pcm/prod/menu/20260309/product/MS_1100_320.png"


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_image_filename_whitelist_and_traversal():
    assert image_filename(URL) == "MS_1100_320.png"
    assert image_filename("https://evil.com/a.png") is None
    assert image_filename("http://menu-img.mcd.cn/a.png") is None
    assert image_filename("https://menu-img.mcd.cn.evil.com/a.png") is None
    assert image_filename("https://menu-img.mcd.cn/x/%2E%2E%2Fetc%2Fpasswd") is None
    assert image_filename("https://menu-img.mcd.cn/x/..") is None
    assert image_filename("https://menu-img.mcd.cn/") is None
    assert image_filename(None) is None


def test_download_success_and_dedupe(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(build_web.urllib.request, "urlopen",
                        lambda url, timeout: calls.append(url) or _Resp(b"PNGDATA"))
    items = {"a": {"image": URL}, "b": {"image": URL}, "c": {"image": None}}
    stats = download_images(items, tmp_path)
    assert calls == [URL]
    assert (tmp_path / "img" / "MS_1100_320.png").read_bytes() == b"PNGDATA"
    assert items["a"]["imageLocal"] == items["b"]["imageLocal"] == "data/img/MS_1100_320.png"
    assert "imageLocal" not in items["c"]
    assert stats["downloaded"] == 1 and stats["failed"] == 0 and stats["bytes"] == 7


def test_skip_existing(tmp_path, monkeypatch):
    (tmp_path / "img").mkdir()
    (tmp_path / "img" / "MS_1100_320.png").write_bytes(b"old")

    def boom(*a, **k):
        raise AssertionError("should not fetch")
    monkeypatch.setattr(build_web.urllib.request, "urlopen", boom)
    items = {"a": {"image": URL}}
    assert download_images(items, tmp_path)["skipped"] == 1
    assert items["a"]["imageLocal"] == "data/img/MS_1100_320.png"


def test_failure_keeps_remote_and_retries(tmp_path, monkeypatch):
    calls = []

    def fail(url, timeout):
        calls.append(url)
        raise urllib.error.URLError("down")
    monkeypatch.setattr(build_web.urllib.request, "urlopen", fail)
    monkeypatch.setattr(build_web.time, "sleep", lambda s: None)
    items = {"a": {"image": URL}}
    stats = download_images(items, tmp_path)
    assert len(calls) == 2 and stats["failed"] == 1
    assert items["a"] == {"image": URL}
    assert not list((tmp_path / "img").iterdir())


def test_rejects_foreign_host(tmp_path, monkeypatch):
    monkeypatch.setattr(build_web.urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no fetch")))
    items = {"a": {"image": "https://evil.com/../x.png"}}
    assert download_images(items, tmp_path)["total"] == 0
    assert "imageLocal" not in items["a"]


def _img_bytes(fmt, size, frames=1):
    from PIL import Image
    buf = io.BytesIO()
    imgs = [Image.new("RGB", size, (200, 40 * i, 30)) for i in range(frames)]
    imgs[0].save(buf, fmt, save_all=frames > 1, append_images=imgs[1:])
    return buf.getvalue()


def test_png_converted_to_webp(tmp_path, monkeypatch):
    from PIL import Image
    monkeypatch.setattr(build_web.urllib.request, "urlopen",
                        lambda url, timeout: _Resp(_img_bytes("PNG", (640, 320))))
    items = {"a": {"image": URL}}
    stats = download_images(items, tmp_path)
    assert items["a"]["imageLocal"] == "data/img/MS_1100_320.webp"
    with Image.open(tmp_path / "img" / "MS_1100_320.webp") as im:
        assert im.format == "WEBP" and max(im.size) == 240 and im.size == (240, 120)
    assert stats["webp"] == 1 and stats["bytes"] == (tmp_path / "img" / "MS_1100_320.webp").stat().st_size
    assert stats["rawBytes"] > 0
    assert not (tmp_path / "img" / "MS_1100_320.png").exists()     # 只保留 WebP


def test_cached_webp_skips_download(tmp_path, monkeypatch):
    (tmp_path / "img").mkdir()
    (tmp_path / "img" / "MS_1100_320.webp").write_bytes(b"cached")
    monkeypatch.setattr(build_web.urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no fetch")))
    items = {"a": {"image": URL}}
    assert download_images(items, tmp_path)["skipped"] == 1
    assert items["a"]["imageLocal"] == "data/img/MS_1100_320.webp"


def test_gif_first_frame(tmp_path, monkeypatch):
    from PIL import Image
    gif_url = URL.replace(".png", ".gif")
    monkeypatch.setattr(build_web.urllib.request, "urlopen",
                        lambda url, timeout: _Resp(_img_bytes("GIF", (300, 300), frames=3)))
    items = {"a": {"image": gif_url}}
    download_images(items, tmp_path)
    assert items["a"]["imageLocal"].endswith(".webp")
    with Image.open(tmp_path / "img" / "MS_1100_320.webp") as im:
        assert getattr(im, "n_frames", 1) == 1 and im.size == (240, 240)


def test_without_pillow_keeps_original(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(build_web, "Image", None)
    monkeypatch.setattr(build_web.urllib.request, "urlopen", lambda url, timeout: _Resp(b"PNGDATA"))
    items = {"a": {"image": URL}}
    stats = download_images(items, tmp_path)
    assert items["a"]["imageLocal"] == "data/img/MS_1100_320.png"
    assert stats["webp"] == 0 and "Pillow" in caplog.text
