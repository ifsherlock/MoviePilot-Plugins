from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import socket
import struct
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from urllib.parse import unquote, urlparse


DEFAULT_CDP = "http://127.0.0.1:39222"
PLUGIN_URL = "https://mp.jaysherlock.top:5443/#/plugin-app/SubtitleManualUpload/main"
WATCH_ASSET = "api/v1/plugin/file/subtitlemanualupload/dist/assets/"
WATCH_API = "/api/v1/plugin/SubtitleManualUpload/"
ROOT = Path(__file__).resolve().parents[1]
LOCAL_ASSETS = ROOT / "plugins.v2" / "subtitlemanualupload" / "dist" / "assets"
DEFAULT_OUT_DIR = ROOT / ".tmp-test-data" / "subtitlemanualupload-ui-backend-refactor-1.3"


class WebSocket:
    def __init__(self, url: str):
        parsed = urlparse(url)
        self.sock = socket.create_connection((parsed.hostname, parsed.port or 80), timeout=10)
        self.sock.settimeout(30)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        path = parsed.path + (f"?{parsed.query}" if parsed.query else "")
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {parsed.hostname}:{parsed.port or 80}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(request.encode("ascii"))
        response = b""
        while b"\r\n\r\n" not in response:
            response += self.sock.recv(4096)
        if b" 101 " not in response.split(b"\r\n", 1)[0]:
            raise RuntimeError(response[:500])

    def send(self, payload: str | bytes, opcode: int = 1) -> None:
        data = payload.encode("utf-8") if isinstance(payload, str) else payload
        first = 0x80 | opcode
        length = len(data)
        if length < 126:
            header = struct.pack("!BB", first, 0x80 | length)
        elif length < 1 << 16:
            header = struct.pack("!BBH", first, 0x80 | 126, length)
        else:
            header = struct.pack("!BBQ", first, 0x80 | 127, length)
        mask = os.urandom(4)
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(data))
        self.sock.sendall(header + mask + masked)

    def recv_exact(self, length: int) -> bytes:
        data = b""
        while len(data) < length:
            chunk = self.sock.recv(length - len(data))
            if not chunk:
                raise EOFError("socket closed")
            data += chunk
        return data

    def recv_message(self) -> str:
        chunks = []
        while True:
            first, second = self.recv_exact(2)
            fin = first & 0x80
            opcode = first & 0x0F
            length = second & 0x7F
            if length == 126:
                length = struct.unpack("!H", self.recv_exact(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", self.recv_exact(8))[0]
            mask = self.recv_exact(4) if second & 0x80 else b""
            payload = self.recv_exact(length) if length else b""
            if second & 0x80:
                payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
            if opcode == 9:
                self.send(payload, opcode=10)
                continue
            if opcode == 8:
                raise EOFError("websocket closed")
            if opcode in (0, 1):
                chunks.append(payload)
                if fin:
                    return b"".join(chunks).decode("utf-8", errors="replace")


class CDPClient:
    def __init__(self, websocket_url: str, out_dir: Path):
        self.ws = WebSocket(websocket_url)
        self.out_dir = out_dir
        self.seq = 0
        self.asset_responses: dict[str, dict] = {}
        self.api_responses: list[dict] = []
        self.failed_plugin_requests: list[dict] = []
        self.console_plugin_errors: list[dict] = []
        self.runtime_exceptions: list[dict] = []

    def handle_event(self, message: dict) -> None:
        method = message.get("method")
        params = message.get("params", {})
        if method == "Network.responseReceived":
            response = params.get("response", {})
            url = response.get("url", "")
            status = response.get("status")
            if WATCH_ASSET in url:
                name = unquote(url.split(WATCH_ASSET, 1)[1].split("?", 1)[0])
                self.asset_responses[name] = {
                    "requestId": params.get("requestId"),
                    "url": url,
                    "status": status,
                    "type": params.get("type"),
                }
            elif WATCH_API in url:
                self.api_responses.append({"url": url, "status": status, "type": params.get("type")})
        elif method == "Network.loadingFailed":
            text = json.dumps(params, ensure_ascii=False)
            if "SubtitleManualUpload" in text or "subtitlemanualupload" in text or "remoteEntry" in text:
                self.failed_plugin_requests.append(params)
        elif method == "Runtime.consoleAPICalled":
            if params.get("type") not in ("error", "warning"):
                return
            text = " ".join(
                str(arg.get("value") or arg.get("description") or "")[:500]
                for arg in params.get("args", [])
            )
            if params.get("type") == "error" or "subtitlemanualupload" in text.lower():
                self.console_plugin_errors.append({"type": params.get("type"), "text": text[:1000]})
        elif method == "Runtime.exceptionThrown":
            self.runtime_exceptions.append(params)

    def send(self, method: str, params: dict | None = None, timeout: int = 30) -> dict:
        self.seq += 1
        message_id = self.seq
        self.ws.send(json.dumps({"id": message_id, "method": method, "params": params or {}}, separators=(",", ":")))
        deadline = time.time() + timeout
        while time.time() < deadline:
            message = json.loads(self.ws.recv_message())
            if message.get("id") == message_id:
                return message
            self.handle_event(message)
        raise TimeoutError(method)

    def pump(self, seconds: float) -> None:
        old_timeout = self.ws.sock.gettimeout()
        self.ws.sock.settimeout(0.25)
        deadline = time.time() + seconds
        while time.time() < deadline:
            try:
                self.handle_event(json.loads(self.ws.recv_message()))
            except socket.timeout:
                pass
        self.ws.sock.settimeout(old_timeout)

    def evaluate(self, expression: str, timeout: int = 30):
        result = self.send(
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True, "awaitPromise": True},
            timeout=timeout,
        )
        payload = result.get("result", {}).get("result", {})
        if "value" in payload:
            return payload["value"]
        return payload.get("description")

    def screenshot(self, name: str) -> str:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        path = self.out_dir / name
        result = self.send("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False}, timeout=60)
        path.write_bytes(base64.b64decode(result["result"]["data"]))
        return str(path)

    def set_viewport(self, width: int, height: int) -> None:
        self.send(
            "Emulation.setDeviceMetricsOverride",
            {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": width <= 430},
        )


def cdp_get(cdp: str, path: str):
    with urllib.request.urlopen(cdp + path, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def browser_page(cdp: str, url_hint: str) -> dict:
    targets = cdp_get(cdp, "/json")
    page = next(
        (
            target
            for target in targets
            if target.get("type") == "page" and "mp.jaysherlock.top" in target.get("url", "")
        ),
        None,
    )
    if page:
        return page
    with urllib.request.urlopen(cdp + "/json/new?" + urllib.parse.quote(url_hint, safe=""), timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_for(client: CDPClient, expression: str, seconds: int = 20):
    deadline = time.time() + seconds
    value = None
    while time.time() < deadline:
        client.pump(0.25)
        value = client.evaluate(expression)
        if value:
            return value
    return value


def click_text(client: CDPClient, text: str, selector: str = "button, [role=button], a, .v-list-item, .media-card"):
    expression = json.dumps(text, ensure_ascii=False)
    selector_json = json.dumps(selector)
    return client.evaluate(
        f"""
        (() => {{
          const needle = {expression};
          const nodes = Array.from(document.querySelectorAll({selector_json}));
          const visible = el => !!(el && el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none');
          const node = nodes.find(el => visible(el) && (el.innerText || el.textContent || '').includes(needle));
          if (!node) return false;
          node.scrollIntoView({{ block: 'center', inline: 'center' }});
          node.click();
          return true;
        }})()
        """
    )


def click_title(client: CDPClient, title: str):
    title_json = json.dumps(title, ensure_ascii=False)
    return client.evaluate(
        f"""
        (() => {{
          const needle = {title_json};
          const nodes = Array.from(document.querySelectorAll('button,[title]'));
          const visible = el => !!(el && el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none');
          const node = nodes.find(el => visible(el) && (el.getAttribute('title') || '').includes(needle));
          if (!node) return false;
          node.scrollIntoView({{ block: 'center', inline: 'center' }});
          node.click();
          return true;
        }})()
        """
    )


def set_search_keyword(client: CDPClient, keyword: str):
    keyword_json = json.dumps(keyword, ensure_ascii=False)
    return client.evaluate(
        f"""
        (() => {{
          const inputs = Array.from(document.querySelectorAll('input.v-field__input, input[type=text]'));
          const input = inputs.find(el => (el.closest('.search-card') || el.getBoundingClientRect().top < 500) && el.offsetWidth > 200);
          if (!input) return false;
          const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
          setter.call(input, {keyword_json});
          input.dispatchEvent(new Event('input', {{ bubbles: true }}));
          input.dispatchEvent(new Event('change', {{ bubbles: true }}));
          return true;
        }})()
        """
    )


def select_online_result(client: CDPClient, provider_name: str = "OpenSubtitles"):
    provider_json = json.dumps(provider_name, ensure_ascii=False)
    return client.evaluate(
        f"""
        (() => {{
          const provider = {provider_json};
          const visible = el => !!(el && el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none');
          const cards = Array.from(document.querySelectorAll('.online-result-card')).filter(visible);
          const card = cards.find(el => !el.classList.contains('disabled') && (el.innerText || '').includes(provider))
            || cards.find(el => !el.classList.contains('disabled'));
          if (!card) return false;
          card.scrollIntoView({{ block: 'center', inline: 'center' }});
          const input = card.querySelector('input[type=checkbox]');
          const control = card.querySelector('.v-selection-control');
          (input || control || card).click();
          return (card.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 240);
        }})()
        """,
        timeout=15,
    )


def summarize_statuses(entries: list[dict]) -> dict[str, list[int]]:
    summary: dict[str, list[int]] = {}
    for entry in entries:
        url = entry["url"]
        key = url.split(WATCH_API, 1)[1].split("?", 1)[0] if WATCH_API in url else url.rsplit("/", 1)[-1]
        summary.setdefault(key, []).append(entry["status"])
    return summary


def wait_for_api(client: CDPClient, endpoint: str, seconds: int = 60) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        client.pump(0.25)
        if any(endpoint in entry["url"] for entry in client.api_responses):
            return True
    return False


def asset_hash_results(client: CDPClient) -> list[dict]:
    results = []
    for name, info in sorted(client.asset_responses.items()):
        body = client.send("Network.getResponseBody", {"requestId": info["requestId"]}, timeout=15).get("result", {})
        raw = body.get("body", "")
        remote = base64.b64decode(raw) if body.get("base64Encoded") else raw.encode("utf-8")
        local_path = LOCAL_ASSETS / name
        local = local_path.read_bytes() if local_path.exists() else None
        results.append(
            {
                "name": name,
                "status": info["status"],
                "remote_len": len(remote),
                "remote_sha256": sha256(remote),
                "local_exists": local_path.exists(),
                "local_len": len(local) if local is not None else None,
                "local_sha256": sha256(local) if local is not None else None,
                "match": remote == local if local is not None else False,
            }
        )
    return results


def run_baseline(cdp: str, out_dir: Path, url: str) -> dict:
    client = CDPClient(browser_page(cdp, url)["webSocketDebuggerUrl"], out_dir)
    for method in ("Page.enable", "Runtime.enable", "Network.enable"):
        client.send(method)
    client.send("Network.setCacheDisabled", {"cacheDisabled": True})
    client.set_viewport(1440, 1000)

    client.send("Page.navigate", {"url": "about:blank"})
    client.pump(1)
    client.send("Page.navigate", {"url": url})
    page_ready = wait_for(client, "document.body?.innerText.includes('字幕匹配')", seconds=30)
    if not page_ready:
        body_text = client.evaluate("document.body?.innerText || ''")
        raise RuntimeError(f"plugin page did not load; visible text starts with: {body_text[:200]!r}")
    client.pump(5)
    entry_text = client.evaluate("document.body?.innerText || ''")
    entry_shot = client.screenshot("entry-1440x1000.png")

    set_search_keyword(client, "百万英镑")
    click_text(client, "搜索", "button")
    wait_for(client, "document.body?.innerText.includes('百万英镑')", seconds=15)
    click_text(client, "百万英镑", ".media-card, button")
    wait_for(client, "document.body?.innerText.includes('本地路径') || document.body?.innerText.includes('目标')", seconds=20)
    client.pump(4)
    detail_text = client.evaluate("document.body?.innerText || ''")
    detail_shot = client.screenshot("target-detail-1440x1000.png")

    online_clicked = click_title(client, "搜索此集在线字幕")
    wait_for(
        client,
        "document.body?.innerText.includes('在线字幕搜索') || document.body?.innerText.includes('选择要下载的字幕')",
        seconds=20,
    )
    wait_for(
        client,
        "document.body?.innerText.includes('OpenSubtitles') || document.body?.innerText.includes('没有可自动下载') || document.body?.innerText.includes('条结果')",
        seconds=60,
    )
    client.pump(4)
    online_text = client.evaluate("document.body?.innerText || ''")
    online_shot = client.screenshot("online-search-1440x1000.png")

    selected_online_result = select_online_result(client)
    preview_ready = wait_for(
        client,
        "Array.from(document.querySelectorAll('button')).some(el => (el.innerText || '').includes('下载并生成预览') && !el.disabled && el.getAttribute('aria-disabled') !== 'true' && !el.classList.contains('v-btn--disabled'))",
        seconds=15,
    )
    before_preview_count = sum(1 for entry in client.api_responses if "online_download_preview" in entry["url"])
    preview_clicked = bool(preview_ready) and click_text(client, "下载并生成预览", "button")
    preview_api_seen = False
    if preview_clicked:
        preview_api_seen = wait_for_api(client, "online_download_preview", seconds=90)
        wait_for(
            client,
            "document.body?.innerText.includes('已下载在线字幕并生成匹配预览') || document.querySelectorAll('.preview-row').length > 0 || document.body?.innerText.includes('已解析') || document.body?.innerText.includes('自动匹配')",
            seconds=60,
        )
        client.pump(4)
    after_preview_count = sum(1 for entry in client.api_responses if "online_download_preview" in entry["url"])
    preview_text = client.evaluate("document.body?.innerText || ''")
    preview_row_count = client.evaluate("document.querySelectorAll('.preview-row').length")
    preview_shot = client.screenshot("online-preview-1440x1000.png")

    ai_clicked = False
    for candidate in ("AI：", "点击查看当前资源任务", "AI:"):
        if click_text(client, candidate):
            ai_clicked = True
            break
    client.pump(3)
    ai_text = client.evaluate("document.body?.innerText || ''")
    ai_shot = client.screenshot("ai-status-1440x1000.png")

    client.send("Page.navigate", {"url": url})
    wait_for(client, "document.body?.innerText.includes('字幕匹配')", seconds=30)
    client.pump(3)
    responsive = []
    for width, height in ((1440, 1000), (768, 1000), (390, 900)):
        client.set_viewport(width, height)
        client.pump(1.5)
        text = client.evaluate("document.body?.innerText || ''")
        responsive.append(
            {
                "viewport": f"{width}x{height}",
                "title_visible": "字幕匹配" in text,
                "content_visible": ("资源选择" in text or "百万英镑" in text or "本地路径" in text),
                "screenshot": client.screenshot(f"responsive-{width}x{height}.png"),
            }
        )

    return {
        "url": url,
        "assets": asset_hash_results(client),
        "entry": {
            "has_title": "字幕匹配" in entry_text,
            "has_resource_selector": "资源选择" in entry_text,
            "screenshot": entry_shot,
        },
        "target_detail": {
            "searched_keyword": "百万英镑",
            "has_movie": "百万英镑" in detail_text,
            "has_local_path": ".mkv" in detail_text and ("/" in detail_text or "\\" in detail_text),
            "has_target_actions": any(word in detail_text for word in ("搜索此集在线字幕", "上传字幕", "调轴", "写入字幕")),
            "has_ai_strip": "AI" in detail_text and ("点击查看" in detail_text or "任务" in detail_text),
            "screenshot": detail_shot,
        },
        "online_search": {
            "clicked": online_clicked,
            "has_opensubtitles": "OpenSubtitles" in online_text,
            "has_online_text": "在线字幕" in online_text,
            "screenshot": online_shot,
        },
        "online_preview": {
            "clicked": preview_clicked,
            "selected_result": selected_online_result,
            "button_ready": bool(preview_ready),
            "api_seen": preview_api_seen,
            "api_count_delta": after_preview_count - before_preview_count,
            "preview_row_count": preview_row_count,
            "has_preview": (
                "已下载在线字幕并生成匹配预览" in preview_text
                or bool(preview_row_count)
                or any(word in preview_text for word in ("已解析", "自动匹配"))
            ),
            "screenshot": preview_shot,
        },
        "ai_status": {
            "clicked": ai_clicked,
            "has_modal_or_task_area": any(word in ai_text for word in ("AI", "任务", "当前资源", "关闭")),
            "screenshot": ai_shot,
        },
        "responsive": responsive,
        "api_statuses": summarize_statuses(client.api_responses),
        "failed_plugin_requests": client.failed_plugin_requests,
        "console_plugin_errors": client.console_plugin_errors,
        "runtime_exceptions_count": len(client.runtime_exceptions),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture SubtitleManualUpload browser baseline through Chrome CDP.")
    parser.add_argument("--cdp", default=DEFAULT_CDP)
    parser.add_argument("--url", default=PLUGIN_URL)
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--json-out", default=None)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    result = run_baseline(args.cdp.rstrip("/"), out_dir, args.url)
    json_path = Path(args.json_out) if args.json_out else out_dir / "baseline.json"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
