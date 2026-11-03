# Troubleshooting

| You see | Fix |
| --- | --- |
| `refused: TODO placeholder ...` (render.py exit 2) | Replace every `TODO` that `yamlreel story` left in the spec. |
| `refused: possible secret ...` (exit 2) | Remove or rename the token or the `password:`/`api_key:` line; specs are burned into frames. |
| `refused: spec ... is outside the current directory` (exit 2) | `cd` to the project folder and keep the spec inside it. |
| `refused: --voice-url must be http(s) on 127.0.0.1 ...` | Voice only works with a local server; otherwise drop `--voice-url`. |
| render.py exit 3, `text shrunk to fit` | Shorten that text (stat values about 8 chars, bullets about 40). |
| render.py exit 3, `cue ... before its row appears` | Move the `at` of the cue later than the row, or lower `stagger`. |
| `scenes[N].xyz: unknown field for a ... scene; allowed: ...` | Fix the spelling or drop the key; use one of the allowed keys. |
| `ffmpeg not found` | `pip install "yamlreel[ffmpeg]"` into the yamlreel venv, or install ffmpeg. |
| `font 'DejaVuSans-Bold.ttf' not found` | macOS: `brew install --cask font-dejavu`. Debian/Ubuntu: `sudo apt install fonts-dejavu-core`. Or set `font_dir` in `~/.config/yamlreel/config.yaml` (ask the user first). |
| `scene N has narration but no voice server is configured` | You ran yamlreel directly; use `render.py` (adds `--no-voice`) or pass `--no-voice`. |
| `<path> exists; pass --force to overwrite` (from `story`) | Pass `--force` only for files you created yourself. |
| `... outside the folders this run may read` | Move the image next to the spec. Do not add `--allow-path` unless the user asks, naming the folder. |
| `capturing a URL needs playwright` | Use a local image instead of a `shot` URL, or ask the user to install `yamlreel[capture]`. |
| Subtitles or narration missing in the output | Expected with `--no-voice`. |
| Question marks or empty boxes instead of CJK text | DejaVu has no CJK glyphs; install Noto Sans CJK and point `font_dir` at it, or keep text Latin. |
| Machine runs out of memory | Render one format at a time (`--format vertical`), preview first, keep videos under about 45s. |
| Python too old / `yamlreel` not found | Run `python3 scripts/check_setup.py`; with the user's yes, `--install`. |
| Windows | Untested upstream; not supported by this skill yet. |
