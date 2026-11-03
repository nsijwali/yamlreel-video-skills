# Writing guide

## Length vs ideas
- 15s: one idea. Hook, one visual, one result.
- 30-45s: one idea plus up to 3 steps.
- Never over 60s for #Shorts (yamlreel adds `#Shorts` to vertical clips up to 60s).
- Scene lengths: `type` 3s, `bullets` 2-2.5s per bullet plus 1s, `code` 6-9s, `stat` 3.5-5s, `cta` 5-6s.

## Hook (first 3 seconds)
- Open with a `type` scene: a question or a surprising claim, under about 50 characters.
- The first still of the contact sheet must make sense on its own: the poster is what viewers see first.
- Avoid "In this video I will..." and anything that needs context.

## Pacing
- Reveal one thing at a time (bullets, diagram edges with `at`). Nothing appears and vanishes in under 2s.
- Vary scene types: do not put three `bullets` scenes in a row.
- Use `transition` sparingly; the default fade is fine.

## Narration vs on-screen text
- On-screen text: short labels and keywords (a bullet is under about 40 characters, a stat value under about 8).
- Narration explains the screen, in one or two sentences; it never reads the bullets aloud.
- Renders default to `--no-voice`, so write narration anyway: it makes a voiced cut possible later, and it drives
  scene length when a voice is used.

## End card
- Finish with a `cta` (a question with up to 4 answers) or a `title` with the name and URL.
- Use `narration: false` on the end card to keep it silent.

## Facts and safety
- Simplifying is fine, being wrong is not. Tell the user to fact-check before publishing.
- Code examples use placeholders (`api_key = "YOUR_KEY"` is still flagged by the secret scan: avoid it).
- `meta.title` (under about 70 chars), `meta.description` (one sentence) and `meta.tags` (no `#`) feed `share-copy.txt`.
- Keep `music.seed` fixed (for example 7) so re-renders are identical.
