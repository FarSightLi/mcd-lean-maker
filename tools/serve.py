"""Local live-mode server: feed web/index.html with a user's own MCD MCP token.

Only standard library. Binds 127.0.0.1 only. Token comes from MCD_MCP_TOKEN.
"""
import argparse
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.parse
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
CACHE_SECONDS = 600


def search_stores(city: str, keyword: str) -> list:
    from mcp_client import call
    result = call("query-nearby-stores", {"searchType": 2, "beType": 1, "city": city, "keyword": keyword})
    if not result.get("success"):
        raise RuntimeError(result.get("message") or "门店搜索失败")
    return [{"storeCode": s["storeCode"], "storeName": s["storeName"], "address": s.get("address", "")}
            for s in (result.get("data") or [])]


class LiveState:
    """Caches the most recently loaded store's live payload for 10 minutes."""

    def __init__(self, collect, search):
        self._collect = collect
        self._search = search
        self._lock = threading.Lock()
        self._store = None
        self._loaded_at = 0.0
        self.current = None

    def search(self, city, keyword):
        return self._search(city, keyword)

    def load(self, store: str, name: str) -> dict:
        with self._lock:
            if self._store == store and self.current is not None and time.monotonic() - self._loaded_at < CACHE_SECONDS:
                return self.current["meta.json"]
            products, meta = self._collect(store, name)
            from build_web import build_payload
            payload = build_payload(products, meta)
            self._store = store
            self._loaded_at = time.monotonic()
            self.current = payload
            return payload["meta.json"]


def make_handler(state: LiveState):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(WEB), **kwargs)

        def log_message(self, format, *args):
            pass

        def _send_json(self, status: int, obj: dict):
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urllib.parse.urlsplit(self.path)
            path, params = parsed.path, urllib.parse.parse_qs(parsed.query)

            if path == "/api/ping":
                return self._send_json(HTTPStatus.OK, {"live": True})

            if path == "/api/stores":
                city, keyword = params.get("city", [""])[0], params.get("keyword", [""])[0]
                if not city or not keyword:
                    return self._send_json(HTTPStatus.BAD_REQUEST, {"error": "缺少 city 或 keyword 参数"})
                try:
                    return self._send_json(HTTPStatus.OK, state.search(city, keyword))
                except Exception as exc:
                    return self._send_json(HTTPStatus.BAD_GATEWAY, {"error": str(exc)})

            if path == "/api/load":
                store, name = params.get("store", [""])[0], params.get("name", [""])[0]
                if not store or not name:
                    return self._send_json(HTTPStatus.BAD_REQUEST, {"error": "缺少 store 或 name 参数"})
                try:
                    return self._send_json(HTTPStatus.OK, state.load(store, name))
                except Exception as exc:
                    return self._send_json(HTTPStatus.BAD_GATEWAY, {"error": str(exc)})

            if path.startswith("/data/") and path.endswith(".json"):
                name = path[len("/data/"):]
                current = state.current
                if current is not None and name in current:
                    return self._send_json(HTTPStatus.OK, current[name])

            return super().do_GET()

    return Handler


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()

    if not os.environ.get("MCD_MCP_TOKEN"):
        sys.exit("MCD_MCP_TOKEN 未设置,实时模式需要先设置该环境变量")

    import snapshot
    state = LiveState(collect=snapshot.collect, search=search_stores)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(state))
    print(f"live server on http://127.0.0.1:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
