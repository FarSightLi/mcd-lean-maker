import re
from pathlib import Path

HTML = (Path(__file__).resolve().parents[1] / "web" / "index.html").read_text(encoding="utf-8")


def test_no_external_assets_except_menu_images():
    urls = re.findall(r'(?:src|href)=["\'](https?://[^"\']+)', HTML)
    assert urls == [], urls
    assert "fonts.googleapis" not in HTML and "cdn." not in HTML


def test_brand_tokens_and_disclaimer():
    assert "#DA291C" in HTML and "#FFC72C" in HTML
    assert "非官方" in HTML and "麦当劳 MCP" in HTML


def test_sections_present():
    for sec in ('id="calc"', 'id="plan"', 'id="new"', 'id="share"', 'id="truth"'):
        assert sec in HTML, sec


def test_live_mode_hooks():
    assert 'id="live-bar"' in HTML and "api/ping" in HTML and "api/load" in HTML


def test_category_menu_hooks():
    assert 'id="cat-nav"' in HTML and 'aria-label="商品分类"' in HTML
    assert "IntersectionObserver" in HTML and "aria-current" in HTML and "data/categories.json" in HTML
    assert "prefers-reduced-motion: reduce" in HTML and "减脂推荐" in HTML
