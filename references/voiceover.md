# Voiceover (optional, bring your own)

The skill renders music-only video by default. Voice is opt-in, and only with a **local** text-to-speech server the
user names.

- yamlreel speaks MCP "Streamable HTTP" and calls the server's `generate_speech` tool, which must return audio
  inline. Any server that does so works.
- Narration text is sent to that server. Keep it on `127.0.0.1`, `localhost` or `::1`: `render.py` refuses any other
  host for `--voice-url`.
- Run: `python3 scripts/render.py videos/<slug>/spec.yaml --voice-url http://127.0.0.1:<port>/mcp/`.
- Each scene's `narration:` is spoken; `narration: false` keeps it silent. Scene length grows to fit the speech.
- To choose a voice or language, the user sets `voiceover: {voice, language}` in their spec or user config. This
  skill ships no voice, voice profile or recording.
- Optional word-by-word captions: add `subtitles: true` to the spec (visible only in voiced renders).
- Do not edit `~/.config/yamlreel/config.yaml` without the user's yes.
- Check the licence of the TTS model before monetising a voiced video.
