import re
from pathlib import Path

HTML = (Path(__file__).resolve().parents[1] / "web" / "index.html").read_text(encoding="utf-8")


SITE = "https://farsightli.github.io/mcd-lean-maker/"
META_TAG = re.compile(r'<meta\s[^>]*>', re.I)


def test_no_external_assets_except_menu_images():
    urls = re.findall(r'(?:src|href)=["\'](https?://[^"\']+)', HTML)
    assert urls == [], urls
    assert "fonts.googleapis" not in HTML and "cdn." not in HTML


def test_absolute_urls_only_in_meta_and_on_site():
    in_meta = [u for tag in META_TAG.findall(HTML) for u in re.findall(r'https?://[^"\'\s>]+', tag)]
    assert in_meta and all(u.startswith(SITE) for u in in_meta), in_meta
    rest = META_TAG.sub("", HTML)
    stray = [u for u in re.findall(r'(?:src|href|content)=["\'](https?://[^"\']+)', rest)]
    assert stray == [], stray


def test_og_tags_and_assets():
    for prop in ('name="description"', 'property="og:title"', 'property="og:description"',
                 'property="og:image"', 'property="og:url"', 'name="twitter:card"'):
        assert prop in HTML, prop
    web = Path(__file__).resolve().parents[1] / "web"
    assert (web / "og.png").is_file() and f'content="{SITE}og.png"' in HTML
    assert (web / "vendor" / "qrcode.js").is_file() and 'src="vendor/qrcode.js"' in HTML
    assert 'rel="icon" href="data:image/svg+xml' in HTML


def test_live_probe_only_on_localhost():
    assert re.search(r"\['localhost',\s*'127\.0\.0\.1'\]\.includes\(location\.hostname\)", HTML)


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
