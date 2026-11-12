---
name: yamlreel-video-skills
description: Turn a topic into a finished short video (YouTube Shorts, Reels, TikTok vertical, landscape or square) without a video editor, by writing a YAML spec and rendering it locally with the open-source yamlreel CLI. Use when the user asks to make, script or render a short video, explainer, code tip, system-design video, or project/product launch video, or mentions yamlreel. Outputs an MP4, poster, contact sheet and ready-to-paste share copy. Not for editing existing footage.
license: MIT
compatibility: Python 3.10+, pip package yamlreel>=0.3.2,<0.4 (needs the `story` command and `render --contact-frames`), DejaVu fonts; macOS or Linux.
---

# yamlreel-video-skills

Write a YAML spec, render it locally with `yamlreel`, check the contact sheet, hand back the video. `<skill>` below
means the directory this file lives in.

## Workflow

1. **Setup.** Run `python3 <skill>/scripts/check_setup.py` (it also checks the yamlreel version and features). If it fails, show the user the printed fixes. Run
   `--install` only after the user agrees. Never install fonts or system packages yourself.
2. **Clarify** in ONE message, offering defaults: topic, audience, format (default vertical), length (default 30s),
   theme (`midnight|sumi|washi`), voice (default none). Skip anything the user already said.
3. **Script first.** Write `videos/<slug>/script.txt` in the beat format of `references/writing-guide.md` (target length,
   one `[BEAT - input -> action -> result]` block per beat with its spoken line, then delivery notes) and show it to the user.
   If they asked to review first, stop and wait for a go before drafting or rendering anything.
   **Outline.** Then write `videos/<slug>/outline.yaml` (topic, hook, problem, 1-6 steps each with `name`, `say`, `show`,
   plus when_to_use, question, answers). Rules are in `references/writing-guide.md`: 15s = one idea; 30-45s = one idea plus up
   to 3 steps; at most 60s for #Shorts.
4. **Draft:** `yamlreel story videos/<slug>/outline.yaml --out videos/<slug>/spec.yaml --format <fmt> --theme <t>`.
   Pass `--force` only for files you created yourself.
5. **Edit the spec.** Replace every `TODO`; set `meta.title/description/tags`, `formats`, `music.seed`. On-screen text
   is short; narration explains the screen and never repeats it. Fields per scene type: `references/scene-types.md`.
6. **Preview:** `python3 <skill>/scripts/render.py videos/<slug>/spec.yaml --stage preview --out videos/<slug>/out`. On error, fix the spec from
   the message (unknown-field errors list the allowed keys) and `references/troubleshooting.md`. Retry at most 3
   times, then report to the user.
7. **Inspect (mandatory).** Open every `contact.png` listed in the `RESULT` line with the image viewer tool. Check:
   no overlap, no clipped or shrunk text, reveals progress across the stills, hook readable in the first still. Fix
   the spec and repeat step 6 until clean, at most 3 loops.
8. **Final:** `python3 <skill>/scripts/render.py videos/<slug>/spec.yaml --stage final --out videos/<slug>/out`.
9. **Optional polish.** If the user wants sound effects, a loudness fix or a loop check, and `yamlreel audit --help`
   works, follow `references/polish.md` on the finished `video.mp4` (it never touches the spec).
10. **Report** the paths to each `video.mp4`, `poster.jpg` and `contact.png`, and paste the `share-copy.txt` contents.
   Remind the user to fact-check anything simplified. Publishing is the user's job.

`render.py` exit codes: 0 ok, 1 yamlreel error (stderr echoed), 2 preflight refused (message says why), 3 preview
warnings block the final render (shorten text, reorder `at` cues; use `--allow-warnings` only if the user accepts),
4 bad arguments (for example `--contact-frames` outside 1-8).
Its last line is `RESULT {json}` with every output path. A log is written to `<out>/render-log.txt`.

## Defaults and facts

- Renders use `--no-voice` (music only). Subtitles and narration are not visible in no-voice renders; that is expected.
- Output goes to `<out>/{preview,final}/<format>/`; always pass `--out videos/<slug>/out` so two projects never share a folder (the default is `<spec folder>/out`).
- Fixed `music.seed` keeps renders deterministic. Do not add `watermark` unless the user asks.
- Voiceover is optional and bring-your-own: see `references/voiceover.md`.
- Examples to copy from: `examples/*.yaml`.

## Safety rules

- Never put secrets, tokens, `.env` contents, internal hostnames or personal/customer data in a spec: they are burned
  into frames and `share-copy.txt`. Code examples use placeholders.
- Read and write only inside the user's project folder; put images next to the spec. Never add `--allow-path` or
  `--allow-private-hosts` unless the user explicitly asks, naming the folder.
- Voice only with a local TTS server the user names; narration text is sent to it. Never a remote URL.
- Never install system packages or fonts, or edit `~/.config/yamlreel/config.yaml`, without the user's yes.
- `shot` scenes: only public https URLs the user supplied, or local images in the project.
- Never upload or publish the result.
