# Optional polish: audit and sound effects

Only for yamlreel releases that have the `audit` and `polish` commands. Check with `yamlreel audit --help`; if it
fails, skip this file (do not raise the required version for it). They work on a finished `video.mp4` and never
change the spec or the render.

## When to use
- The user asks for sound effects, louder or quieter audio, or a Shorts/Reels loop.
- Before handing back a video with music or a voice: run the audit, report its `warn` lines.

## Commands
```bash
yamlreel audit videos/<slug>/out/final/vertical/video.mp4
yamlreel polish videos/<slug>/out/final/vertical/video.mp4 --loudness -14 --out videos/<slug>/out/final/vertical/video-polished.mp4
yamlreel polish video.mp4 --sfx videos/<slug>/sfx.yaml --out video-polished.mp4
```

- `audit` prints `ok`/`warn`: loudness against -14 LUFS (within 2), true peak (warn above -1 dBTP), loop
  (last frame should lead into the first), and the 60 s Shorts limit for vertical video.
- `polish --loudness -14` normalises and limits peaks; the result is close to the target, not exact. Re-run `audit` on it.
- `polish --sfx` mixes timed effects. `sfx.yaml`:

  ```yaml
  sfx:
    - {at: 1.8, kind: tap}                 # kinds: tap thump clatter splash scrape whoosh pop click tick rustle ping
    - {at: 6.8, kind: clatter, gain: 0.8}  # gain 0 to 2, default 0.5
    - {at: 8.0, file: meow.wav}            # the user's own recording, in the same folder as sfx.yaml
  ```

## Rules
- Write the polished file next to the original under a new name; never overwrite the original and never pass `--force`
  on a file you did not create.
- Built-in effects are synthetic. For natural sound, ask the user to record or supply a file; do not download audio
  from the web, and never use a recording whose licence the user has not confirmed.
- You cannot hear the result. Say that, and report the `audit` numbers instead of claiming it sounds good.
- Never pass `--allow-path` unless the user names the folder.
