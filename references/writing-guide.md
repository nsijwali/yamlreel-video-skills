# Writing guide

## Length vs ideas
- 15s: one idea. Hook, one visual, one result.
- 30-45s: one idea plus up to 3 steps.
- Never over 60s for #Shorts (yamlreel adds `#Shorts` to vertical clips up to 60s).
- Scene lengths: `type` 3s, `bullets` 2-2.5s per bullet plus 1s, `code` 6-9s, `stat` 3.5-5s, `cta` 5-6s.

## Hook (first 3 seconds)
- Open with a relatable problem the viewer has met, shown on screen, not the topic name: "A test passes alone, then fails in
  the suite." Spoken hook about 15 words or fewer. Do not preview the answer; any "here are five..." bridge is one short line.
- A `type` scene with the claim works; for diagrams, show the problem happening (nodes flashing as failures).
- The first still of the contact sheet must make sense on its own: the poster is what viewers see first.
- Avoid "In this video I will..." and anything that needs context.

## Script format (write this before the spec)
```
TITLE - SCRIPT
Target: about 50-55 seconds

[HOOK - one shared logger branches to five tests; the tests fail]
Spoken line.

[BEAT NAME - input -> pattern action -> result]
Spoken line, about 18 words or fewer.

DELIVERY NOTES
- 2-3 short notes: pauses, what must stay on screen long enough to read, how it ends.
```
- One idea per beat. Show cause and effect (a request enters, the pattern acts, the result appears) with `diagram`
  `edges` and `flash` cues; never hold a static code card for a whole beat.
- About 130 spoken words is roughly 50-55 seconds.
- Recap in single words on screen long enough to read, state the caveat ("use it when the problem appears"), then ask
  the question and end right after it. Add "tell me in the comments" if you want replies.

## Headlines, section tags and the end question
- Give every beat a short headline of two beats that carry the idea ("Bursty in. Steady out.", "Watch. Scale. Slow the
  intake."), so the idea survives with the sound off.
- Number the beats with a small section tag above the headline ("01 / THE BURST", "05 / WHEN THE LINE KEEPS GROWING").
  This is the `kicker` field on data scenes (`bullets`, `code`, `diagram`, `table`, `array`, `meter`, `grid`, `tree`,
  `timeline`); it needs a yamlreel newer than 0.3.1. On older versions put the tag in the headline text instead.
- Show a growing backlog, a filling cache or a draining budget with a `meter` bar so the viewer watches the number
  climb, instead of stacking items over a label (stacked items can collide with the label above them).
- End with a two-option question that is easy to answer in one word: a `cta` scene with two `answers` ("A short wait" or
  "A timeout") is easier to answer in a comment than an open question.

## Cover and share copy
- Cover (hook frame): thin inset frame; top row with the channel name left and a series tag ("TOPIC / 01") right over a
  hairline; a kicker in the accent colour; a three-line bold serif headline with the last word in the accent; the
  diagram; a bold tracked caption; a one-line footer tagline.
- Share copy: a benefit-led title ("5 Design Patterns That Solve Everyday Engineering Headaches"), one sentence naming
  the items, then three hashtags (`#Shorts` plus two topic tags).

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
- Code examples use placeholders (`api_key = "YOUR_KEY"` passes the secret scan; real-looking values and `secret: <value with digits>` do not).
- `meta.title` (under about 70 chars), `meta.description` (one sentence) and `meta.tags` (no `#`) feed `share-copy.txt`.
- Keep `music.seed` fixed (for example 7) so re-renders are identical.
