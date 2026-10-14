import json
import threading
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from serve import LiveState, make_handler

SNAP = Path(__file__).resolve().parents[1] / "web" / "snapshot"
PRODUCTS = json.loads((SNAP / "products.json").read_text(encoding="utf-8"))


def fake_collect(store, name):
    return PRODUCTS, {"storeCode": store, "storeName": name, "productCount": len(PRODUCTS), "snapshotAt": "now"}


def fake_search(city, keyword):
    return [{"storeCode": "1", "storeName": f"{city}{keyword}店", "address": "x"}]


def serve():
    state = LiveState(collect=fake_collect, search=fake_search)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(state))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, state


def get(srv, path):
    quoted = urllib.parse.quote(path, safe="/?=&")
    with urllib.request.urlopen(f"http://127.0.0.1:{srv.server_address[1]}{quoted}") as r:
        return json.loads(r.read())


def test_live_routes():
    srv, state = serve()
    try:
        assert srv.server_address[0] == "127.0.0.1"
        assert get(srv, "/api/ping") == {"live": True}
        assert get(srv, "/api/stores?city=北京&keyword=国贸")[0]["storeName"] == "北京国贸店"
        meta = get(srv, "/api/load?store=1&name=测试店")
        assert meta["storeName"] == "测试店"
        assert get(srv, "/data/meta.json")["storeName"] == "测试店"
        assert "1100" in get(srv, "/data/items.json")
    finally:
        srv.shutdown()


def test_cache_reuses_payload():
    calls = []
    state = LiveState(collect=lambda s, n: (calls.append(s), fake_collect(s, n))[1], search=fake_search)
    state.load("1", "a")
    state.load("1", "a")
    assert calls == ["1"]


def test_missing_param_400():
    srv, _ = serve()
    try:
        try:
            get(srv, "/api/load")
            raise AssertionError("expected 400")
        except urllib.error.HTTPError as e:
            assert e.code == 400 and "error" in json.loads(e.read())
    finally:
        srv.shutdown()
