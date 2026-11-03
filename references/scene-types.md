# Scene types

Every scene takes `type`, `seconds`, and optionally `caption` (lower third), `narration` (string, or `false` for
silent), `step`, `transition`, `energy`. For voiced renders also `subtitles` (bool), `keywords` (words to highlight in
the subtitles), `narration_words` (path to a JSON file of `{word, start, end}` entries) and `narration_audio` (path
to a .wav file); keep both files next to the spec. Unknown keys are errors. `bullets`, `table` and `array` reveal
their items with `stagger` (seconds between items). Each block below is validated by `tests/e2e.py`
(wrapped as the only scene of a spec).

## title
Eyebrow, title, subtitle and URL easing in line by line. Fields: `title`, `eyebrow`, `subtitle`, `url`.
```yaml
- type: title
  eyebrow: System design in under a minute
  title: Cache stampede
  subtitle: One expiry, ten thousand queries.
  seconds: 3
```

## type
One line typed out with a cursor: the hook. Field: `text` (keep under about 50 characters).
```yaml
- type: type
  text: What is a cache stampede?
  seconds: 3
```

## bullets
Points that appear one at a time. Fields: `title`, `items` (short), `stagger` (0.1-3 s between bullets).
```yaml
- type: bullets
  title: The fix
  items: [Let one request rebuild the key, Serve stale while it refreshes, Add jitter to every TTL]
  stagger: 1.2
  seconds: 8
```

## code
Code typed on screen. Fields: `code`, `highlight` (1-based line numbers), `title` (file name). Use placeholders only.
```yaml
- type: code
  title: lock.py
  code: |
    def get(key):
        value = cache.get(key)
        return value or rebuild(key)
  highlight: [3]
  caption: One request rebuilds.
  seconds: 7
```

## stat
One big number or phrase. Fields: `value`, `label`, `eyebrow`, `count` (`true` counts up; `value` must hold one
number). Keep `value` short (about 8 characters) or it shrinks and warns.
```yaml
- type: stat
  eyebrow: Result
  value: "10,000"
  label: queries per expiry
  count: true
  seconds: 4
```

## table
Rows appear one by one; optional scan bar, highlighted row and ticking counter. Fields: `title`, `columns` (1-6),
`rows` (1-12, one cell per column, cells up to 40 chars), `stagger`, `reveal: all`, `scan`, `highlight`, `counter`.
```yaml
- type: table
  title: users
  columns: [id, name]
  rows:
    - [1, Ada]
    - [2, Lin]
    - [3, Kim]
  stagger: 0.4
  scan: {at: 1.5, per_row: 0.3, stop: 2, color: accent}
  highlight: [{row: 2, at: 2.6, text: found, color: accent2}]
  seconds: 6
```

## array
One row of cells with sorted inserts, pushes, pops, marks and a window. Fields: `title`, `items` (0-12), `steps`
(up to 40; each has `at` and one of `insert`, `push`, `pop: front|back`, `mark: [idx]`, `window: [a, b]`,
`unmark: true`).
```yaml
- type: array
  title: A job queue
  items: [job1, job2]
  steps:
    - {at: 1.0, push: job3}
    - {at: 2.0, pop: front}
    - {at: 3.0, window: [0, 1], text: next up}
  seconds: 5
```

## cta
End card: question bubble, up to 4 lettered answers, pulsing prompt. Fields: `question` (required), `answers`,
`prompt`.
```yaml
- type: cta
  question: Which strategy do you use?
  answers: [Round robin, Least connections, Something else]
  prompt: Answer in the comments
  seconds: 6
```

## diagram
Boxes and arrows appearing in order. `nodes`: `id, label, kind (client|service|cache|db), x, y, vx, vy, at`
(x/y are 0-1 fractions; `vx`/`vy` override them in vertical frames). `edges`: `from, to, label, bad, dashed, at,
color`. `flash`: `node, at, text, color`. Do not draw two labelled edges on the same path (labels overlap).
```yaml
- type: diagram
  title: One hot key
  nodes:
    - {id: users, label: Users, kind: client, x: 0.15, y: 0.46, vx: 0.4, vy: 0.2}
    - {id: cache, label: Cache, kind: cache, x: 0.5, y: 0.46, vx: 0.4, vy: 0.4}
    - {id: db, label: Database, kind: db, x: 0.85, y: 0.46, vx: 0.4, vy: 0.6}
  edges:
    - {from: users, to: cache, label: GET}
    - {from: cache, to: db, label: miss, bad: true, at: 3.0}
  flash:
    - {node: db, at: 4.0, text: overloaded}
  seconds: 7
```

## shot
A screenshot of a public https URL or a local image next to the spec, with a slow camera move. A URL needs
`pip install "yamlreel[capture]"` and `playwright install chromium`, which this skill does not set up: prefer local
images. Fields: `source`, `title`, `fit: cover|card`, `zoom: [from, to]`, `focus: [x, y]`.
```yaml
- type: shot
  source: https://example.com
  fit: card
  zoom: [1.0, 1.2]
  seconds: 5
```
