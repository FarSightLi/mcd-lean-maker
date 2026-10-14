"""Maintainer-only MCP client. Token comes from MCD_MCP_TOKEN."""
import json
import os
import urllib.request

MCP_URL = os.environ.get("MCD_MCP_URL", "https://mcp.mcd.cn")


def _token() -> str:
    token = os.environ.get("MCD_MCP_TOKEN")
    if not token:
        raise SystemExit("MCD_MCP_TOKEN 未设置")
    return token


def call(tool: str, args: dict) -> dict:
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": tool, "arguments": args}}).encode()
    req = urllib.request.Request(MCP_URL, data=body, headers={
        "Authorization": f"Bearer {_token()}", "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"})
    raw = urllib.request.urlopen(req, timeout=30).read().decode()
    if raw.startswith("event:") or raw.startswith("data:"):
        raw = [line[5:] for line in raw.splitlines() if line.startswith("data:")][-1]
    text = json.loads(raw)["result"]["content"][0]["text"]
    # the payload is embedded after markdown field docs
    obj, _ = json.JSONDecoder().raw_decode(text[text.find('{"success"'):])
    return obj
