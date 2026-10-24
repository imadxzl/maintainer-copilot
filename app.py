"""Maintainer Copilot playground: try the triage bot without a GitHub account.

Runs the exact same triage logic as the GitHub Action (triage.py), checks for
duplicates against the demo repo's real open issues, and shows the comment it
would post. Nothing is posted anywhere. Standard library only.

    python app.py            -> http://localhost:8000

Environment (or .env): GEMINI_API_KEY (required), DEMO_REPO (default
imadxzl/maintainer-copilot), GITHUB_TOKEN (optional, raises GitHub's rate limit),
RATE_LIMIT (default 5 per 10 min per visitor), MAX_CONCURRENT (default 3), PORT.
"""

import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import triage

ROOT = Path(__file__).parent
DEMO_REPO = os.environ.get("DEMO_REPO", "imadxzl/maintainer-copilot")
RATE_LIMIT = int(os.environ.get("RATE_LIMIT", 5))
RATE_WINDOW = 600
MAX_CONCURRENT = int(os.environ.get("MAX_CONCURRENT", 3))
MAX_BODY = 8 * 1024 * 1024
ISSUES_TTL = 300

_hits, _hits_lock = {}, threading.Lock()
_slots = threading.BoundedSemaphore(MAX_CONCURRENT)
_issues_cache = {"at": 0, "items": []}


def rate_limited(ip):
    now = time.time()
    with _hits_lock:
        recent = [t for t in _hits.get(ip, []) if now - t < RATE_WINDOW]
        limited = len(recent) >= RATE_LIMIT
        if not limited:
            recent.append(now)
        _hits[ip] = recent
        if len(_hits) > 10_000:
            for k in [k for k, v in _hits.items() if not v or now - v[-1] > RATE_WINDOW]:
                del _hits[k]
        return limited


def open_issues():
    """The demo repo's open issues, cached so we stay under GitHub's unauthenticated rate limit."""
    if time.time() - _issues_cache["at"] > ISSUES_TTL:
        try:
            _issues_cache["items"] = triage.GitHub(DEMO_REPO).open_issues()
            _issues_cache["at"] = time.time()
        except Exception as e:  # keep serving with the last good list
            print("could not refresh issues:", e, flush=True)
    return _issues_cache["items"]


def playground_triage(title, body, image):
    others = open_issues()
    issue = {"number": max([o["number"] for o in others], default=0) + 1,
             "title": title, "body": body, "user": {"login": "you"}}
    images, notes = triage.fetch_images(body)  # screenshots linked in the text
    if image:
        images = [image] + images[:triage.MAX_IMAGES - 1]
    result = triage.normalize(triage.gemma(issue, others, images), issue, others)
    return {"result": result, "comment": triage.render(result, len(images)),
            "labels": {name: "#" + triage.LABELS[name][0] for name in result["labels"]},
            "issue_number": issue["number"], "checked_against": len(others), "notes": notes}


class Handler(BaseHTTPRequestHandler):
    def client_ip(self):
        return ((self.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
                or self.client_address[0])

    def send_json(self, code, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path, ctype):
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/":
            return self.send_file(ROOT / "static" / "index.html", "text/html; charset=utf-8")
        if path == "/samples/ci-403-error.png":
            return self.send_file(ROOT / "samples" / "ci-403-error.png", "image/png")
        if path == "/api/issues":
            return self.send_json(200, {"repo": DEMO_REPO, "issues": [
                {"number": i["number"], "title": i["title"], "url": i["html_url"]} for i in open_issues()]})
        self.send_error(404)

    def do_POST(self):
        if self.path != "/api/triage":
            return self.send_error(404)
        length = int(self.headers.get("Content-Length", 0))
        if length > MAX_BODY:
            return self.send_json(413, {"error": "Too large. Keep screenshots under 5 MB."})
        try:
            req = json.loads(self.rfile.read(length) or b"{}")
            title, body, image = (req.get("title") or "").strip(), req.get("body") or "", req.get("image")
        except Exception:
            return self.send_json(400, {"error": "Bad request."})
        if not title:
            return self.send_json(400, {"error": "Give the issue a title."})
        if image and image.get("mime") not in triage.IMAGE_TYPES:
            return self.send_json(400, {"error": "Screenshots must be PNG, JPEG or WebP."})
        if rate_limited(self.client_ip()):
            return self.send_json(429, {"error": f"You've hit the limit of {RATE_LIMIT} triages per "
                                                 f"{RATE_WINDOW // 60} minutes. Try again shortly."})
        if not _slots.acquire(blocking=False):
            return self.send_json(503, {"error": "Busy triaging other issues. Try again in a few seconds."})
        try:
            self.send_json(200, playground_triage(title[:256], body[:20_000], image))
        except Exception as e:
            self.send_json(500, {"error": str(e)})
        finally:
            _slots.release()

    def log_message(self, fmt, *args):
        print("  " + fmt % args, flush=True)


if __name__ == "__main__":
    if not triage.API_KEY:
        raise SystemExit("GEMINI_API_KEY is not set (env var or .env file).")
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0" if "PORT" in os.environ else "127.0.0.1")
    print(f"Maintainer Copilot playground on http://{host}:{port} (repo: {DEMO_REPO})", flush=True)
    ThreadingHTTPServer((host, port), Handler).serve_forever()
