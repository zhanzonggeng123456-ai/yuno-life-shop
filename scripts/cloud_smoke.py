"""Exercise an isolated localhost container, never a live customer deployment."""
import argparse
import base64
import hashlib
import json
import os
import secrets
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:18000"
PHOTO = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=")


def request(path, data=None, token=None, content_type="application/json"):
    headers = {}
    if token:
        headers["Authorization"] = "Bearer " + token
    if isinstance(data, dict):
        data = json.dumps(data).encode()
    if data is not None:
        headers["Content-Type"] = content_type
    with urllib.request.urlopen(urllib.request.Request(BASE + path, data=data, headers=headers), timeout=10) as r:
        return json.load(r) if "application/json" in r.headers.get("Content-Type", "") else r.read()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["create", "verify"])
    parser.add_argument("--state", required=True, type=Path)
    args = parser.parse_args()
    for attempt in range(30):
        try:
            assert request("/healthz")["ok"]
            break
        except (urllib.error.URLError, TimeoutError):
            if attempt == 29:
                raise
            time.sleep(1)
    assert request("/")["payment"] == "simulated"
    if args.mode == "create":
        result = request("/api/v1/actions/register", {
            "email": secrets.token_hex(12) + "@example.jp", "display_name": "Container QA",
            "password": secrets.token_urlsafe(24)})
        token = result["token"]
        boundary = secrets.token_hex(12)
        body = (f'--{boundary}\r\nContent-Disposition: form-data; name="name"\r\n\r\nCloud QA\r\n'
                f'--{boundary}\r\nContent-Disposition: form-data; name="photo"; filename="photo.png"\r\n'
                'Content-Type: image/png\r\n\r\n').encode() + PHOTO + f'\r\n--{boundary}--\r\n'.encode()
        draft = request("/api/v1/actions/oneclick_upload", body, token,
                        "multipart/form-data; boundary=" + boundary)
        state = {"token": token, "user_id": result["user"]["id"], "draft_id": draft["id"]}
        # This temporary file contains only disposable CI credentials. Never log it.
        with args.state.open("x", encoding="utf-8") as f:
            os.chmod(args.state, 0o600)
            json.dump(state, f)
    else:
        state = json.loads(args.state.read_text(encoding="utf-8"))
        assert request("/api/v1/me", token=state["token"])["user"]["id"] == state["user_id"]
        draft = request(f'/api/v1/drafts/{state["draft_id"]}', token=state["token"])["item"]
        assert len(draft["photos"]) == 1
        assert hashlib.sha256(request(draft["photos"][0]["url"])).digest() == hashlib.sha256(PHOTO).digest()
    print("YUNO container " + args.mode + ": passed")


if __name__ == "__main__":
    main()
