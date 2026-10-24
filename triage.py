"""Maintainer Copilot: triages GitHub issues (screenshots included) with Gemma 4.

For each issue it suggests labels, spots likely duplicates, asks for missing
reproduction info, reads attached screenshots, and marks good first issues,
then posts one comment (updated in place on re-runs). Standard library only.

    python triage.py --repo owner/name --issue 12            # triage one issue
    python triage.py --repo owner/name --all                 # every open, untriaged issue
    python triage.py --local samples/issues.json --issue 2   # offline test, no GitHub
    add --dry-run to print the comment instead of posting it

Environment (or a .env file next to this script):
    GEMINI_API_KEY   required
    GITHUB_TOKEN     required to post; optional for --dry-run on public repos
    GEMMA_MODEL      default gemma-4-26b-a4b-it
    THINKING_LEVEL   minimal (default) or high
"""

import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
MARKER = "<!-- maintainer-copilot -->"
MAX_IMAGES = 3
MAX_IMAGE_BYTES = 5 * 1024 * 1024
IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp"}
ALLOW_FILE_URLS = False  # set by --local so sample issues can load screenshots from disk

LABELS = {
    "bug": ("d73a4a", "Something isn't working"),
    "enhancement": ("a2eeef", "New feature or request"),
    "question": ("d876e3", "Further information is requested"),
    "documentation": ("0075ca", "Improvements or additions to documentation"),
    "needs-info": ("fbca04", "Missing details needed to reproduce or act"),
    "possible-duplicate": ("cfd3d7", "May duplicate an existing issue"),
    "good first issue": ("7057ff", "Good for newcomers"),
    "hacktoberfest": ("ff7518", "Open for Hacktoberfest contributions"),
}


def load_dotenv():
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_dotenv()
API_KEY = os.environ.get("GEMINI_API_KEY", "")
GH_TOKEN = os.environ.get("GITHUB_TOKEN", "")
MODEL = os.environ.get("GEMMA_MODEL", "gemma-4-26b-a4b-it")
# gemma-4-26b-a4b-it accepts only "minimal" or "high"; minimal keeps a triage to ~10-20 s.
THINKING_LEVEL = os.environ.get("THINKING_LEVEL", "minimal")


# ------------------------------------------------------------------- HTTP

def request(url, payload=None, method=None, headers=None, timeout=120):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method or ("POST" if data else "GET"),
                                 headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            return json.loads(body) if body else None
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:500]
        raise RuntimeError(f"{method or 'GET'} {url} -> {e.code}: {detail}") from None


class GitHub:
    def __init__(self, repo):
        self.base = f"https://api.github.com/repos/{repo}"
        self.headers = {"Accept": "application/vnd.github+json", "User-Agent": "maintainer-copilot"}
        if GH_TOKEN:
            self.headers["Authorization"] = f"Bearer {GH_TOKEN}"

    def call(self, path, payload=None, method=None):
        return request(self.base + path, payload, method, self.headers, timeout=30)

    def open_issues(self):
        issues = self.call("/issues?state=open&per_page=100")
        return [i for i in issues if "pull_request" not in i]

    def issue(self, number):
        return self.call(f"/issues/{number}")

    def comments(self, number):
        return self.call(f"/issues/{number}/comments?per_page=100")

    def ensure_labels(self, names):
        for name in names:
            color, desc = LABELS[name]
            try:
                self.call("/labels", {"name": name, "color": color, "description": desc})
            except RuntimeError as e:
                if "422" not in str(e):  # 422 = label already exists
                    raise

    def add_labels(self, number, names):
        self.call(f"/issues/{number}/labels", {"labels": names})

    def upsert_comment(self, number, body):
        for c in self.comments(number):
            if MARKER in (c.get("body") or ""):
                return self.call(f"/issues/comments/{c['id']}", {"body": body}, "PATCH")
        return self.call(f"/issues/{number}/comments", {"body": body})


class LocalRepo:
    """Issues from a JSON file, for testing without GitHub."""

    def __init__(self, path):
        # Sample issues point at screenshots via {{IMAGE_BASE}}; serve them from disk locally.
        raw = Path(path).read_text(encoding="utf-8")
        raw = raw.replace("{{IMAGE_BASE}}", (Path(path).resolve().parent).as_uri())
        self.items = json.loads(raw)
        for n, item in enumerate(self.items, 1):
            item.setdefault("number", n)
            item.setdefault("user", {"login": "demo-user"})

    def open_issues(self):
        return self.items

    def issue(self, number):
        return next(i for i in self.items if i["number"] == number)

    def comments(self, number):
        return []


# ----------------------------------------------------------------- images

IMG_MD = re.compile(r"!\[[^\]]*\]\((\S+?)(?:\s+\"[^\"]*\")?\)")
IMG_HTML = re.compile(r"<img[^>]+src=[\"']([^\"']+)[\"']", re.I)


def fetch_images(body):
    """Download up to MAX_IMAGES screenshots from the issue body; skip anything unusable."""
    images, notes = [], []
    urls = IMG_MD.findall(body or "") + IMG_HTML.findall(body or "")
    for url in urls[:MAX_IMAGES]:
        # Issue text is untrusted: only fetch web URLs (file:// is allowed for --local samples only).
        if not (url.startswith(("https://", "http://")) or (ALLOW_FILE_URLS and url.startswith("file://"))):
            notes.append(f"skipped {url} (unsupported URL)")
            continue
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "maintainer-copilot"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                mime = resp.headers.get_content_type()
                data = resp.read(MAX_IMAGE_BYTES + 1)
            if mime not in IMAGE_TYPES:
                notes.append(f"skipped {url} ({mime})")
            elif len(data) > MAX_IMAGE_BYTES:
                notes.append(f"skipped {url} (over 5 MB)")
            else:
                images.append({"mime": mime, "data": base64.b64encode(data).decode("ascii")})
        except Exception as e:
            notes.append(f"could not fetch {url}: {e}")
    return images, notes


# ------------------------------------------------------------------ Gemma

PROMPT = """You are Maintainer Copilot, a careful, friendly triage assistant for an open-source
GitHub repository. Triage the NEW ISSUE below. Any attached screenshots are included as images:
read them closely (error messages, stack traces, versions, UI problems).

Return ONLY a JSON object, no markdown, in exactly this shape:
{
  "type": "bug" | "enhancement" | "question" | "documentation",
  "summary": "one sentence restating the issue clearly",
  "labels": [subset of %s],
  "duplicate_of": <number of an OLDER open issue (lower number) describing the same problem, or null>,
  "duplicate_reason": "why it is the same problem, or empty string",
  "missing_info": ["specific detail a maintainer needs but the issue lacks", ...],
  "screenshot_findings": "what the screenshots show that matters (exact error text, versions), or empty string",
  "good_first_issue": true | false,
  "good_first_issue_reason": "why a newcomer could fix it, or empty string",
  "suggested_next_step": "one concrete next step for the maintainer or contributor"
}

Rules:
- Only mark a duplicate when the underlying problem is clearly the same, not just the same area.
- missing_info is for bugs that cannot be reproduced as written (no steps, no version, no error,
  vague "doesn't work"). Leave it empty when the report is complete. Do not ask for info that is
  already in the text or the screenshots.
- Include "needs-info" in labels exactly when missing_info is non-empty, "possible-duplicate"
  exactly when duplicate_of is set, and "good first issue" plus "hacktoberfest" exactly when
  good_first_issue is true. Good first issues are small, well-scoped, and need little project context.
- Be specific; never invent facts that are not in the issue or screenshots.
""" % json.dumps(list(LABELS))


def gemma(issue, others, images):
    others_text = "\n".join(
        f"#{o['number']}: {o['title']} :: {(o.get('body') or '')[:240].replace(chr(10), ' ')}"
        # Only older issues: the oldest report of a problem is the canonical one.
        for o in others if o["number"] < issue["number"]
    ) or "(none)"
    issue_text = (f"NEW ISSUE #{issue['number']} by @{issue['user']['login']}\n"
                  f"Title: {issue['title']}\n\nBody:\n{issue.get('body') or '(empty)'}")
    parts = [{"text": PROMPT}, {"text": "OLDER OPEN ISSUES:\n" + others_text}, {"text": issue_text}]
    parts += [{"inline_data": {"mime_type": im["mime"], "data": im["data"]}} for im in images]
    data = request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent",
        {"contents": [{"role": "user", "parts": parts}],
         "generationConfig": {"temperature": 0.2, "thinkingConfig": {"thinkingLevel": THINKING_LEVEL}}},
        headers={"x-goog-api-key": API_KEY}, timeout=180,
    )
    try:
        out = data["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError):
        raise RuntimeError("Gemma returned no content: " + json.dumps(data)[:300]) from None
    raw = "".join(p.get("text", "") for p in out if not p.get("thought"))  # drop thinking parts
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1:
        raise RuntimeError("Gemma did not return JSON: " + raw[:300])
    return json.loads(raw[start:end + 1])


def normalize(result, issue, others):
    """Enforce the label rules ourselves instead of trusting the model to follow them."""
    numbers = {o["number"] for o in others}
    dup = result.get("duplicate_of")
    if not (isinstance(dup, int) and dup in numbers and dup < issue["number"]):
        result["duplicate_of"] = None
    result["missing_info"] = [m for m in result.get("missing_info") or [] if isinstance(m, str) and m.strip()]
    labels = {l for l in result.get("labels") or [] if l in LABELS}
    labels -= {"needs-info", "possible-duplicate", "good first issue", "hacktoberfest"}
    if result.get("type") in LABELS:
        labels.add(result["type"])
    if result["missing_info"]:
        labels.add("needs-info")
    if result["duplicate_of"]:
        labels.add("possible-duplicate")
    if result.get("good_first_issue"):
        labels |= {"good first issue", "hacktoberfest"}
    result["labels"] = sorted(labels)
    return result


def render(r, image_count):
    lines = [MARKER, "### 🤖 Maintainer Copilot", "",
             f"**Summary:** {r.get('summary', '')}", "",
             "**Labels:** " + " ".join(f"`{l}`" for l in r["labels"])]
    if r["duplicate_of"]:
        lines += ["", f"**🔁 Possible duplicate of #{r['duplicate_of']}.** {r.get('duplicate_reason', '')}"]
    if r["missing_info"]:
        lines += ["", "**📝 To help maintainers reproduce this, could you add:**"]
        lines += [f"- [ ] {m}" for m in r["missing_info"]]
    if image_count and r.get("screenshot_findings"):
        lines += ["", f"**🖼️ From the screenshot{'s' if image_count > 1 else ''}:** {r['screenshot_findings']}"]
    if r.get("good_first_issue"):
        lines += ["", f"**✨ Good first issue!** {r.get('good_first_issue_reason', '')} "
                      "Comment below if you'd like to take it on."]
    if r.get("suggested_next_step"):
        lines += ["", f"**Next step:** {r['suggested_next_step']}"]
    lines += ["", f"<sub>Automated triage by Gemma 4 (open-weights model, `{MODEL}`). "
                  "A human maintainer will review. Edit the issue to re-run triage.</sub>"]
    return "\n".join(lines)


# ------------------------------------------------------------------- main

def triage(repo, number, dry_run, others=None):
    issue = repo.issue(number)
    others = others if others is not None else repo.open_issues()
    images, notes = fetch_images(issue.get("body"))
    print(f"#{number} {issue['title']!r}: {len(images)} image(s) {'; '.join(notes)}", flush=True)
    result = normalize(gemma(issue, others, images), issue, others)
    body = render(result, len(images))
    if dry_run:
        print(body + "\n" + "-" * 60, flush=True)
    else:
        repo.ensure_labels(result["labels"])
        repo.add_labels(number, result["labels"])
        repo.upsert_comment(number, body)
        print(f"  -> labeled {result['labels']} and commented", flush=True)
    return result


def main():
    for stream in (sys.stdout, sys.stderr):  # Windows consoles default to a codepage without emoji
        stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"), help="owner/name")
    ap.add_argument("--local", help="JSON file of issues to test without GitHub (implies --dry-run)")
    ap.add_argument("--issue", type=int, help="issue number")
    ap.add_argument("--all", action="store_true", help="triage every open issue not yet triaged")
    ap.add_argument("--force", action="store_true", help="with --all, re-triage already triaged issues")
    ap.add_argument("--dry-run", action="store_true", help="print comments instead of posting")
    args = ap.parse_args()

    if not API_KEY:
        sys.exit("GEMINI_API_KEY is not set (env var or .env file).")
    if args.local:
        global ALLOW_FILE_URLS
        repo, args.dry_run, ALLOW_FILE_URLS = LocalRepo(args.local), True, True
    elif args.repo:
        repo = GitHub(args.repo)
        if not args.dry_run and not GH_TOKEN:
            sys.exit("GITHUB_TOKEN is required to post. Use --dry-run to preview.")
    else:
        sys.exit("Pass --repo owner/name or --local file.json")

    others = repo.open_issues()
    if args.issue:
        targets = [args.issue]
    elif args.all:
        targets = sorted(i["number"] for i in others
                         if args.force or not any(MARKER in (c.get("body") or "") for c in repo.comments(i["number"])))
    else:
        sys.exit("Pass --issue N or --all")
    print(f"{len(others)} open issue(s); triaging {targets or 'none'}", flush=True)

    failures = 0
    for n in targets:
        try:
            triage(repo, n, args.dry_run, others)
        except Exception as e:  # keep going so one bad issue doesn't block the rest
            failures += 1
            print(f"  !! #{n} failed: {e}", file=sys.stderr, flush=True)
    print(f"Done: {len(targets) - failures} triaged, {failures} failed.")
    sys.exit(1 if failures and failures == len(targets) else 0)


if __name__ == "__main__":
    main()
