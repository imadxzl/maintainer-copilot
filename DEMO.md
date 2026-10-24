# Maintainer Copilot: Demo Kit

**Playground:** https://maintainer-copilot.vercel.app/ · **Repo:** https://github.com/imadxzl/maintainer-copilot · **Live issues:** https://github.com/imadxzl/maintainer-copilot/issues

## 1. Two-minute pitch script (solo)

You present and drive the laptop yourself. The script files a real issue **at 0:25**. The comment takes about 15 seconds to appear, and you talk through that time, so you never stand in silence.

**Before you start, open three browser tabs:**
1. The **Issues** list, showing the colored labels.
2. **New issue**, with the title already typed: `Action crashes when posting the comment` and `samples/ci-403-error.png` (or any Python traceback screenshot) ready to drag in.
3. Issue **#3**, the duplicate.

Zoom to 125% so the back row can read it.

| Time | Say | Do |
|---|---|---|
| 0:00–0:15 | "Hacktoberfest brings thousands of new contributors to open source, and thousands of new issues. Many say only *'it doesn't work'*, repeat an existing issue, or are just a screenshot of an error that nobody can search. Maintainers burn out triaging them." | Issues tab |
| 0:15–0:25 | "Maintainer Copilot is a GitHub Action powered by **Gemma 4**. It reads every new issue, **including screenshots**, and triages it before a human has to." | Point at the labels |
| 0:25–0:35 | "Let me file a bug the lazy way: no description, just a screenshot of an error." | **Drag in the screenshot and click Submit** |
| 0:35–0:55 | *(while the Action runs)* "Behind the scenes, an Action starts within two seconds. It sends the issue text, the screenshot as an image, and the list of older issues to Gemma 4 in a single call, and asks for structured JSON. My code, not the model, has the final say: labels come only from a fixed list, and a duplicate must point to a real, older issue. So a weird issue can't make the bot invent labels." | Refresh the issue |
| 0:55–1:15 | "There it is, about 15 seconds after I filed it. It read the **exact error out of the image**, a 403, 'Resource not accessible by integration', plus the line number and versions, and suggested the actual fix: a token permissions problem." | Point at the 🖼️ line and the Next step |
| 1:15–1:30 | "It also catches duplicates. This issue is worded completely differently from #1, but Copilot spotted that it's the same crash and explained why." | Tab 3: issue #3 |
| 1:30–1:45 | "Vague reports get a checklist asking for exactly what's missing. Small, well-scoped fixes get tagged **good first issue** and **hacktoberfest**, so new contributors can find their first PR." | Back to Issues: point at #2 and #4 |
| 1:45–2:00 | "Two files, one secret, five minutes to install. And you can try it right now at maintainer-copilot.vercel.app, no account needed. Maintainer Copilot. Thank you!" | Playground page |

**If a judge asks…**
- *"What if the model is wrong?"* It never closes or edits issues. It only labels and comments, and every comment says a human maintainer will review. Labels are restricted to an allowlist enforced in code.
- *"What about spam or prompt injection in issues?"* Issues are untrusted input. The code restricts the model's possible actions to allowlisted labels and one comment, which it updates rather than duplicating. That limits what a malicious issue can do.
- *"Does it spam threads?"* No. There's one comment per issue, and when someone edits the issue, it updates that comment in place.
- *"What was hard?"*
  - Gemma 4's default thinking was slow. Setting `thinkingLevel: minimal` brought it to about 5 seconds per issue (this model rejects `low`).
  - Issues created by the Action's own token don't trigger other workflows, so the demo seeder triages in the same job.
  - GitHub's issue list lags a few seconds behind newly created issues. I found this from a run that "succeeded" while doing nothing, then added a wait and logging.
  - An early version told the *older* issue to close as a duplicate of the newer one. Now only older issues are offered as duplicate candidates.
- *"Why Gemma?"* It's open-weights and multimodal, so it reads screenshots. Because the weights are open, the same triage can run on a maintainer's own hardware.

---

## 2. Backup plan

Network trouble is the main risk. Drop down a layer if one fails:

1. **Live issue** (best). File a fresh issue with a screenshot. Do one test run about 5 minutes before you present.
   - If GitHub Actions is slow, use the **playground** (https://maintainer-copilot.vercel.app/) instead. Click **🖼️ Screenshot only**, then **Submit**. You get the same triage in about 12 seconds.
2. **The issues already triaged.** If the live Action is slow, skip filing and walk through #5 (screenshot), #3 (duplicate), #2 (needs-info) and #4 (good first issue). They're already on GitHub.
3. **Local dry run.** `python triage.py --local samples/issues.json --issue 5` prints the comment in the terminal. It needs the Gemini API, but not GitHub.
4. **Pre-recorded video.** Record yourself filing an issue and refreshing until the comment appears, about 60 seconds.
   - **Windows 11:** Snipping Tool → *Record* (`Win + Shift + R`), or Xbox Game Bar (`Win + Alt + R`).
   - Upload it to YouTube as **Unlisted** for the submission form, and keep the local file on the desktop.
5. **Screenshots.** Save PNGs of the issues list and of the #5 and #3 comments.

**Reset the demo if you want a clean repo:** close the test issues, then run **Actions → Seed demo issues** again. It skips titles that already exist and only triages issues it hasn't triaged yet.

---

## 3. Submission text

### Project name
Maintainer Copilot

### Links
- **Try it (no account needed):** https://maintainer-copilot.vercel.app/
- **Code:** https://github.com/imadxzl/maintainer-copilot
- **See it working:** https://github.com/imadxzl/maintainer-copilot/issues (every issue was triaged by the bot)

### Tagline (one line)
A GitHub Action that triages every new issue, screenshots included, with Gemma 4: it adds labels, spots duplicates, asks for missing info and finds good first issues, all in about 15 seconds.

### Inspiration
Hacktoberfest is great for open source, but it floods maintainers with issues: vague reports, duplicates, and screenshots of stack traces nobody can search. Triage is the unpaid, invisible work that burns maintainers out. I wanted a first-pass triager any project can install in five minutes, built on an open model.

### What it does
When an issue is opened, edited or reopened, Maintainer Copilot:
- **Labels it** `bug`, `enhancement`, `question` or `documentation`.
- **Spots duplicates** of older open issues and explains the match.
- **Asks for missing info** with a checklist when a bug can't be reproduced as written, and adds `needs-info`.
- **Reads screenshots**, pulling exact error text, line numbers and versions out of images.
- **Finds good first issues** and tags them `good first issue` + `hacktoberfest` for newcomers.
- **Suggests a next step** for the maintainer.

It posts **one comment per issue** and updates it in place on edits, so it never spams a thread.

### How I built it
- **Model:** Gemma 4 (`gemma-4-26b-a4b-it`) through the Gemini API. One call per issue carries the issue text, up to 3 screenshots as inline images, and the list of older open issues, and returns strict JSON.
- **Code enforces the rules:** labels come only from an allowlist. Duplicates must reference a real, older, open issue. `needs-info`, `possible-duplicate` and `good first issue` are derived from the structured fields, not trusted from the model's own label list.
- **Platform:** a GitHub Actions workflow using the built-in `GITHUB_TOKEN` (issues: write). There's a manual mode to triage an existing backlog, plus a one-click demo seeder.
- **Zero dependencies:** a single Python file using only the standard library. Installing means copying two files and adding one secret.
- **Playground:** a web page on Vercel that runs the same triage code on an issue you type, checks duplicates against the repo's real open issues, and previews the comment without posting. It's rate-limited per visitor and refuses non-web image links from untrusted input.

### Challenges I ran into
- **Latency from thinking.** Gemma 4 reasons by default and was slow. `thinkingLevel: minimal` brought triage down to about 5 seconds per issue. This model accepts `minimal` and `high` but rejects `low`.
- **GitHub Actions details:** issues created with the Action's token don't trigger other workflows, and the issue list lags a few seconds behind new issues. I caught the second one from a run that reported success while triaging nothing, then added a wait and logging.
- **Duplicate direction:** an early version told an *older* issue to close as a duplicate of a newer one. Now only older issues are offered as candidates, so the original report stays canonical.
- **Windows console encoding** crashed on the 🤖 emoji during local testing. A small fix, but it hid otherwise good results.

### Accomplishments I'm proud of
- **14 seconds** from filing an issue to a posted triage comment, fully automatic.
- On 6 realistic demo issues it got every call right: needs-info on the vague one, the duplicate linked to the right original, good first issues on the small fixes, and the **exact 403 error read from a screenshot-only bug report** with the correct permissions diagnosis.
- Given an off-topic screenshot (a Windows blue screen), it labeled it a `question` and asked whether it was filed by mistake rather than inventing a bug.

### What I learned
How to make an open model safe to run on untrusted input: let it judge, but have code decide what it's allowed to do. I also learned a lot about the quirks of GitHub Actions events and permissions.

### What's next
- Similarity search (embeddings) for duplicates across closed issues and large repos.
- Learning each repository's own labels and contributing guidelines.
- Automatically opening a PR for trivial good first issues such as typos.
- GitLab support and a fully local Ollama mode for self-hosted projects.

### Built with
`gemma-4` · `gemini-api` · `github-actions` · `github-rest-api` · `python` · `javascript` · `vercel`

---

### Category-specific blurbs (paste into each category's field if the form asks "why does this fit?")

**Best Use of Gemma 4**
> Maintainer Copilot is a focused AI tool for the open-source community, built entirely around Gemma 4. It's **multimodal where it matters**: bug reports are often just a screenshot of an error, and Gemma reads the exact error text, line numbers and versions out of the image to triage them. It shows **rapid prototyping**: one structured Gemma 4 call per issue, tuned with a `minimal` thinking level, gets a new issue from filing to a triage comment in about 14 seconds. It's running live: https://github.com/imadxzl/maintainer-copilot/issues

**Best Open-Source AI Project (DigitalOcean)**
> Maintainer Copilot is an open-source (MIT) agent for open-source maintainers, built on an open-weights model, Gemma 4. It works like an agent skill for a repository: it observes new issues and acts within a safe, code-enforced action space (allowlisted labels and one comment that updates in place). It helps with the unglamorous work that keeps projects alive: triaging, de-duplicating, asking for repro details, and surfacing good first issues for newcomers. It's one dependency-free Python file and installs in five minutes: https://github.com/imadxzl/maintainer-copilot
