# Spec: yamlreel-video Agent Skill

Status: proposed · Repo: github.com/nsijwali/yamlreel-video (MIT) · Target: yamlreel >=0.3.0,<0.4 (placeholder, unreleased; see MIN_VERSION in scripts/check_setup.py)

## 1. Problem and requirements
Agents can write a script but cannot hand back a finished short video without a video editor. yamlreel renders a YAML
spec into `video.mp4`, `poster.jpg`, `contact.png` and `share-copy.txt` locally. The skill teaches an agent to drive it.

Functional
- F1 Turn a topic into a rendered video in vertical (1080x1920), landscape (1920x1080) or square (1080x1080).
- F2 Prescribed workflow: clarify, outline, `yamlreel story`, edit, validate, preview, inspect contact sheet, fix, final render, share copy.
- F3 `scripts/check_setup.py` reports Python, venv, yamlreel version, ffmpeg, DejaVu fonts, and can install yamlreel on request.
- F4 `scripts/render.py` runs preflight -> validate -> preview -> contact-sheet check -> final render and prints output paths.
- F5 Three ready specs (system-design explainer, code tip, product launch) that render with `--no-voice`.
- F6 Voiceover optional, bring-your-own local TTS; default is `--no-voice`.

Quality attributes: works offline after install; no personal data in repo; scripts are stdlib-only Python and run on
macOS + Linux; deterministic outputs (fixed music `seed`); SKILL.md stays short (detail lives in `references/`).

## 2. Constraints and assumptions
- Skill format follows the Agent Skills spec: `SKILL.md` with YAML frontmatter; `name` is lowercase/hyphens, at most
  64 chars, and must match the install directory; `description` at most 1024 chars. Claude Code loads it from
  `~/.claude/skills/<name>/` or `.claude/skills/<name>/`.
- MCP Market submission is the public repo URL. Assumed: it detects `SKILL.md` at repo root. Confirm before submitting.
- yamlreel facts relied on (from its README and `yamlreel/cli.py`; the required range is `VERSION_SPEC` in `scripts/check_setup.py`, currently `>=0.3.0,<0.4`, with unreleased builds accepted when `check_setup.probe_features` passes): commands `init`, `story`, `validate`,
  `render`; flags `--preview` (half size, 12 fps), `--no-voice`, `--out`, `--format`, `--contact-frames 1-8`,
  `--voice-url`, `--music`; `render` exits 0 even with warnings, prints `  <fmt>: <path> (<s>s, WxH)` to stdout,
  `  warning: ...` lines and `error: ...` (exit 1) to stderr, and `share copy: <path>`; `story` refuses to overwrite
  without `--force`, accepts one `--format`, and leaves `TODO` placeholders; unknown spec keys are errors; fonts are
  DejaVu (`DejaVuSans-Bold.ttf` etc.); ffmpeg comes from PATH or the `[ffmpeg]` extra.
- `--no-voice` strips narration, so subtitles are not visible in no-voice renders (expected, not a bug).
- macOS fonts need `brew install --cask font-dejavu`; the skill never runs brew itself.
- Windows is untested upstream; the skill documents it as unsupported for now.

## 3. Proposed design
### 3.1 Repo layout
```
SKILL.md                     agent instructions + frontmatter (< 150 lines)
README.md                    GitHub / MCP Market page: what it does, demo image link, requirements, install, license
LICENSE                      MIT, "Nitin Sijwali"
scripts/check_setup.py       environment check / optional install
scripts/render.py            preflight + validate + preview + check + final render wrapper
references/scene-types.md    one minimal valid snippet + main fields per scene type (10 types)
references/writing-guide.md  hooks, pacing, length vs ideas, narration vs on-screen text, end cards
references/troubleshooting.md  error -> fix table (upstream table + skill-specific rows)
references/voiceover.md      optional BYO local TTS (MCP Streamable HTTP, generate_speech); no profile ids
examples/system-design-rate-limiter.yaml   ~30s vertical+landscape: type, diagram, bullets, stat, cta
examples/code-tip-python.yaml              ~15s vertical: type, code (highlight), stat
examples/product-launch.yaml               ~20s vertical+square: type, bullets, stat, title (fictional product, example.com)
tests/e2e.py                 renders every example + validates every cheatsheet snippet
.github/workflows/ci.yml     ubuntu, py3.10+3.12, fonts-dejavu-core, runs tests/e2e.py --preview
```
Examples contain `narration:` lines (good practice; stripped by `--no-voice`), `music.seed: 7`, no `watermark`, no
`shot` scenes (avoids Playwright and network), no TODOs. Nothing from the author's config, voice or videos is included.

### 3.2 SKILL.md frontmatter
```yaml
name: yamlreel-video
description: Turn a topic into a finished short video (YouTube Shorts, Reels, TikTok vertical, landscape or square)
  without a video editor, by writing a YAML spec and rendering it locally with the open-source yamlreel CLI. Use when
  the user asks to make, script or render a short video, explainer, code tip, system-design video, or project/product
  launch video, or mentions yamlreel. Outputs an MP4, poster, contact sheet and ready-to-paste share copy. Not for
  editing existing footage.
license: MIT
compatibility: Python 3.10+, pip package yamlreel>=0.3.0,<0.4, DejaVu fonts; macOS or Linux.
```

### 3.3 Workflow SKILL.md prescribes
1. Setup: run `python3 <skill>/scripts/check_setup.py`. If it fails, show the fixes; run `--install` only after the user agrees.
2. Clarify (one message, defaults offered): topic, audience, format (default vertical), length (default 30s), theme
   (`midnight|sumi|washi`), voice (default none). Do not ask about anything the user already said.
3. Outline: write `videos/<slug>/outline.yaml` (topic, hook, problem, 1-6 steps with `show`, when_to_use, question).
   Rules from `references/writing-guide.md`: 15s = one idea; 30-45s = one idea + up to 3 steps; at most 60s for #Shorts.
4. `yamlreel story videos/<slug>/outline.yaml --out videos/<slug>/spec.yaml --format <fmt> --theme <t>`.
5. Edit: replace every `TODO`, set `meta.title/description/tags`, `formats`, `music.seed`; on-screen text short,
   narration explains (never duplicates) the screen. Consult `references/scene-types.md` for fields.
6. `python3 <skill>/scripts/render.py videos/<slug>/spec.yaml --stage preview` (run from the project folder). On error, fix using the message (unknown-field errors
   list allowed keys) and `references/troubleshooting.md`; retry at most 3 times, then report to the user.
7. Open every printed `contact.png` with the image viewer tool. Check: no overlap, no clipped or shrunk text, reveals
   progress across stills, hook readable in the first still. Fix the spec and repeat step 6 until clean, max 3 loops.
8. `python3 <skill>/scripts/render.py videos/<slug>/spec.yaml --stage final` (run from the project folder).
9. Report: paths to each `video.mp4`, `poster.jpg`, `contact.png`, and paste `share-copy.txt` contents. Remind the user to
   fact-check anything simplified.

### 3.4 scripts/check_setup.py (stdlib only, runs on python3 >= 3.8 so it can report "too old")
- CLI: `check_setup.py [--install] [--json]`. Candidates in order: `$YAMLREEL_BIN`, `$YAMLREEL_VENV/bin/yamlreel`
  (default venv `~/.yamlreel/venv`), then `yamlreel` on PATH. The first candidate that is usable wins and unusable ones
  are skipped (`find_yamlreel`, shared with render.py, so the approved binary is the one that renders). Usable means:
  `--version` (15s timeout) runs, and a feature probe passes (`story --help`, `render --help` lists `--contact-frames`,
  and `validate` accepts a spec using table, array, cta, stagger, transition, energy and music lofi), and the version is
  in `>=0.3.0,<0.4` OR it is an unreleased build, i.e. older than 0.3.0 but passing the probe. A version >= 0.4 is
  rejected even if the probe passes; the message names the supported range and says to downgrade or pin. Each binary is
  assessed once per process (cache keyed by realpath, mtime and size). render.py reports "no usable yamlreel (wrong
  version or missing features)" when candidates exist but none is usable, and "yamlreel not found" when there are none.
- Checks, each printed `ok|fail <name>: <detail> [fix: <command>]`: Python >= 3.10 interpreter available (finds
  `python3.12/3.11/3.10/python3`); venv exists; `yamlreel --version` >= 0.3.0 and < 0.4; ffmpeg via `shutil.which` or the
  venv's `imageio_ffmpeg.get_ffmpeg_exe()`; DejaVu `DejaVuSans.ttf`, `DejaVuSans-Bold.ttf`, `DejaVuSansMono.ttf` found
  in `$YAMLREEL_FONT_DIR`, `~/Library/Fonts`, `/Library/Fonts`, `/usr/share/fonts/**`, `~/.local/share/fonts/**`; and a
  smoke render (1-scene `title`, 1s, `--preview --no-voice --music none --format square`) in a temp dir, which is the
  authoritative check because it exercises yamlreel's own font and ffmpeg lookup.
- `--install`: create the venv with the found Python >= 3.10, `pip install "yamlreel[ffmpeg]>=0.3.0,<0.4"`. Never
  installs fonts or system packages; prints the brew/apt command instead.
- Exit 0 all ok, 1 any fail. `--json` prints `{"ok": bool, "checks": [{name, ok, detail, fix}], "yamlreel": path}`.

### 3.5 scripts/render.py (stdlib only)
- CLI: `render.py SPEC [--stage preview|final|all] [--out DIR] [--format F] [--contact-frames N]
  [--voice-url URL] [--allow-warnings]`. Default stage `all`; default out `<spec folder>/out`, with
  `preview/` and `final/` subfolders so the preview never overwrites the final.
- Preflight (exit 2 on refusal, message says why): spec and out dir resolve inside the current working directory
  (or the skill's `examples/`); spec has no `TODO` outside comments; secret scan (`find_secret` in render.py: provider
  key prefixes such as `AKIA...`, `sk-`, `ghp_`, `xox`/`xapp-`, `hf_`, `npm_`, `SG.`, JWTs, `-----BEGIN`, Bearer tokens,
  URL passwords (empty user allowed), `Authorization: Basic <base64>`, and keyword assignments where the keyword
  `password|passwd|secret|secret_key|token|api_key|private_key|access_key` ENDS the identifier (`client_secret`,
  `GITHUB_TOKEN`, `SECRET_KEY` match; `token_bucket`, `password_hash`, `author`, `pwd_context` do not; bare `auth` and
  `pwd` are not keywords) followed by `:`/`=` and a value, with plain, escaped or doubled quotes; quoted values may hold
  spaces. Exempt: placeholders such as `YOUR_KEY`, `<...>`, `xxx`, `${VAR}`, `$ALLCAPS_VAR`, ALLCAPS_NAMES; a quoted
  value equal to the keyword (`"password"`); a bare value that is code (contains any of `( ) [ ] { } ,` or `$(`) or
  contains the keyword itself; hyphenated prose like `secret: rate-limiting`);
  `--voice-url` host must be `127.0.0.1`, `localhost` or `::1` over http(s) and must not contain `user:password@`. Without `--voice-url` every render gets
  `--no-voice`, so a remote `voice_server` in the user config is never used by the skill.
- Steps: `yamlreel validate SPEC` (print its `ok:` line) -> `yamlreel render SPEC --preview --out OUT/preview
  --contact-frames N(default 3)` -> check each format's `contact.png` exists, has a PNG signature and nonzero IHDR size
  -> if preview warnings and not `--allow-warnings`, exit 3 before final -> `yamlreel render SPEC --out OUT/final`.
- Never passes `--allow-path`, `--allow-private-hosts` or `--read-screen`.
- Output: human lines, then one final line `RESULT {json}` with `stage, ok, warnings[], formats{fmt: {video, poster,
  contact, seconds, size}}, share_copy`. Parses yamlreel stdout lines; paths are absolute.
- Exit codes: 0 ok, 1 yamlreel error (its stderr is echoed, URL credentials scrubbed), 2 preflight refused, 3 warnings
  block final, 4 usage error.
- Appends every command, exit code and stderr to `OUT/render-log.txt`.

### 3.6 Safety rules (in SKILL.md, enforced where possible by render.py)
- Never put secrets, tokens, `.env` contents, internal hostnames or personal/customer data in a spec: they are burned
  into frames and `share-copy.txt`. Code examples use placeholders.
- Only read/write inside the user's project folder; images go next to the spec. Never add `--allow-path` or
  `--allow-private-hosts` unless the user explicitly asks, naming the folder.
- Voice only with a local TTS server the user names; narration text is sent to it. Never a remote URL.
- Never install system packages, fonts or edit `~/.config/yamlreel/config.yaml` without the user's yes.
- `shot` scenes: only public https URLs the user supplied, or local images in the project.
- Publishing is the user's job; the skill never uploads.

## 4. Alternatives considered
- MCP server wrapping yamlreel: more moving parts (process, transport, schemas) for no gain; the CLI is the interface.
- Bash wrappers: brittle output parsing and portability; stdlib Python is already required.
- Vendoring or auto-pinning yamlreel in the repo: duplicates an MIT package already on PyPI; pip install is simpler.
- Single-shot full render: wastes minutes on broken layouts; preview + contact sheet catches them in seconds.
- Font check by importing yamlreel internals: couples to private APIs; the smoke render is authoritative and stable.
- Skill in a `skills/yamlreel-video/` subfolder: cleaner for multi-skill repos but complicates clone-install and
  submission. Root layout + explicit clone target wins for one skill.
- `allowed-tools` frontmatter: experimental and client-specific; omit, rely on normal permission prompts.
- Auto-installing fonts via brew: system change without consent; print the command instead.

## 5. Rollout and compatibility
- New repo; nothing to migrate. Install: `git clone https://github.com/nsijwali/yamlreel-video ~/.claude/skills/yamlreel-video`
  (the target name must equal `name`; README says so in bold). Project-scoped: `.claude/skills/yamlreel-video`.
- Tag `v0.1.0` once acceptance passes on macOS and CI is green; then submit the repo URL to mcpmarket.com.
- Pin `yamlreel>=0.3.0,<0.4`. On a yamlreel minor release: rerun `tests/e2e.py`, update cheatsheet, widen pin, tag.

## 6. Risks, failure modes, edge cases, observability
- Upstream schema change breaks examples/cheatsheet: pin + e2e test that validates every snippet.
- Agent skips viewing `contact.png`: SKILL.md makes it a numbered, mandatory step; RESULT JSON lists the paths.
- Low-RAM machines: preview first, one format at a time is yamlreel's behaviour; keep examples at most 30s and 2 formats.
- Fonts present but in an odd folder: smoke render fails; fix row points to `font_dir` in user config.
- `story` target exists: wrapper is not involved; SKILL.md says pass `--force` only for files the agent itself created.
- Text shrink / cue-before-row warnings: exit 3 blocks final; agent shortens text or reorders `at` cues.
- Narration in spec but no voice: always `--no-voice` by default, so no "no voice server" error.
- Secret-scan false positives (e.g. a code tip about API keys): message names the line; user can rename the token.
- Non-ASCII/CJK text needs Noto CJK; documented in troubleshooting.
- Observability: `render-log.txt`, RESULT JSON line, `check_setup.py --json`.

## 7. Test plan (builder must satisfy)
- `tests/e2e.py [--preview]`: for each `examples/*.yaml`, `scripts/render.py <ex> --stage all --out <tmp>/<stem>`
  exits 0 with zero warnings; every format folder has `video.mp4` (> 50 KB), `poster.jpg`, `contact.png`; RESULT
  `seconds` within 10% of the spec's summed `seconds`; `share-copy.txt` contains `meta.title`.
- Every fenced `yaml` block in `references/scene-types.md` passes `yamlreel validate` when wrapped as a one-scene spec.
- render.py preflight unit cases: spec outside cwd -> 2; `TODO` in spec -> 2; secret strings (see `tests/e2e.py` `secret_cases`) -> 2; placeholders -> pass; `--voice-url
  https://api.example.com/mcp/` or any URL with userinfo -> 2; `--voice-url http://127.0.0.1:3900/mcp/` passes preflight; warning fixture -> 3.
- check_setup.py: passes on a configured Mac; `find_yamlreel` skips binaries that fail the version/feature probe (order:
  `$YAMLREEL_BIN`, skill venv, PATH) and check_setup fails if it approved a different binary than render.py would run;
  an empty `YAMLREEL_FONT_DIR` adds nothing and the smoke render stays authoritative.
- Repo hygiene grep: no `profile id`, no personal paths (`/Users/`), no author watermark, no `.wav` files.
- Frontmatter: `name` matches `^[a-z0-9-]{1,64}$`, description <= 1024 chars.
- Manual macOS end to end (acceptance): fresh shell, `check_setup.py --install`, then a full (non-preview) render of
  each of the 3 examples with `--no-voice` succeeds; open each `contact.png` and play each MP4. Then in Claude Code,
  prompt "make a 15 second Short about Python f-string debugging" and confirm the skill triggers and follows 3.3.

## 8. Implementation steps (one PR each)
1. LICENSE, README skeleton, SKILL.md frontmatter + workflow (3.2, 3.3, 3.6).
2. `scripts/check_setup.py` with `--json`, `--install`, smoke render.
3. `scripts/render.py` preflight + stages + RESULT line + log; preflight unit tests.
4. Three examples; render each locally with `--no-voice`, inspect contact sheets, tune timing.
5. `references/scene-types.md` (all 10 types) + snippet validation in `tests/e2e.py`.
6. `references/writing-guide.md`, `troubleshooting.md`, `voiceover.md`.
7. `tests/e2e.py` full + CI workflow; hygiene grep.
8. README final (install, requirements, example contact sheet image rendered from examples), macOS acceptance, tag v0.1.0, submit.
