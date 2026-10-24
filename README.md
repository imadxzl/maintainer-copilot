# Maintainer Copilot 🤖

**Issue triage for open-source maintainers, powered by Gemma 4. Screenshots included.**

Open-source maintainers drown in issues: vague bug reports, duplicates, and screenshots of stack traces that nobody can search. Maintainer Copilot is a GitHub Action that reads every new issue, **including attached screenshots**, with Gemma 4 (an open-weights multimodal model). It then:

- 🏷️ **Labels it**: `bug`, `enhancement`, `question` or `documentation`.
- 🔁 **Spots duplicates** of older open issues and explains why they match.
- 📝 **Asks for missing info** with a checklist (steps, versions, logs) when a bug can't be reproduced as written, and adds `needs-info`.
- 🖼️ **Reads screenshots**: it pulls the exact error text and versions out of images of logs and UIs.
- ✨ **Finds good first issues** and tags them `good first issue` + `hacktoberfest`, so newcomers can find them.
- ➡️ **Suggests a next step** for the maintainer.

It posts **one comment per issue** and updates that comment in place whenever the issue is edited, so it never spams the thread.

## Example
For an issue whose only content is a screenshot of a failing CI log, Copilot replied:

> **From the screenshot:** The log shows a RuntimeError: POST …/issues/7/comments -> 403: "Resource not accessible by integration". Version: maintainer-copilot v0.3.1, Python 3.12.3.
>
> **Next step:** Investigate if this is a permission issue with the GitHub token used in the workflow (e.g., missing 'write' permissions for issues) rather than a code bug.

## Add it to your repo (5 minutes)
1. Copy `triage.py` and `.github/workflows/maintainer-copilot.yml` into your repo.
2. Get a Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey).
3. Go to **Settings → Secrets and variables → Actions → New repository secret**. Name it `GEMINI_API_KEY` and paste the key.
4. Open an issue. Triage appears in about 30 seconds.

To triage existing issues, go to **Actions → Maintainer Copilot → Run workflow** and leave the issue number empty.

## Try the demo
In this repo, run **Actions → Seed demo issues → Run workflow**. It creates six realistic issues (a full bug report, a vague one, a duplicate, a typo, a screenshot-only CI failure and a feature request) and triages them all.

## Playground (no GitHub account needed)
`app.py` is a small web page that runs the **same triage logic** on an issue you type, optionally with a screenshot. It checks duplicates against this repo's real open issues and shows the labels and comment the bot would post. Nothing is posted. Run it with `python app.py` and open http://localhost:8000. To deploy it, import the repo on Vercel (or any Python host) and set `GEMINI_API_KEY`. Each visitor gets 5 triages per 10 minutes.

## Run locally
There are no dependencies to install, only Python's standard library.
```bash
cp .env.example .env                                     # add GEMINI_API_KEY
python triage.py --local samples/issues.json --all       # offline sample issues, prints comments
python triage.py --repo owner/name --issue 12 --dry-run  # preview on a real public repo
```

## How it works
- `triage.py` fetches the issue and the older open issues through the GitHub REST API, and downloads up to 3 screenshots (PNG/JPEG/WebP, 5 MB max each).
- It makes **one Gemma 4 call** (`gemma-4-26b-a4b-it` through the Gemini API) containing the issue text, the screenshots as inline images, and a list of older issues, and asks for strict JSON.
- **The code enforces the rules; the model doesn't get the final say.** Labels come only from a fixed allowlist. Duplicates must point to a real, older, open issue. `needs-info`, `possible-duplicate` and `good first issue` are derived from the structured fields, not trusted from the model's label list.
- Gemma's thinking is set to `minimal`. The default thinking made calls much slower, and the `minimal` setting triages an issue in about 5 seconds.

## Limits
- Issue text and screenshots come from anyone who can open an issue, so the model sees untrusted input. The allowlisted labels and code-enforced rules limit what a malicious issue can do, but the comment text itself is model-generated. Maintainers should treat it as a suggestion.
- Only older issues (up to the 100 most recent open ones) are checked for duplicates.

## License
MIT
