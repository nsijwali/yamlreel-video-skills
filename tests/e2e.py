#!/usr/bin/env python3
"""End-to-end and hygiene tests for the yamlreel-video skill. Stdlib only.

Usage: tests/e2e.py [--preview]
  --preview  render examples with --stage preview only (fast, used in CI); default runs --stage all.
Needs yamlreel on PATH, $YAMLREEL_BIN, or the skill venv (see scripts/check_setup.py).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
from check_setup import find_yamlreel  # noqa: E402

RENDER = SCRIPTS / "render.py"
CHECK = SCRIPTS / "check_setup.py"
YAMLREEL = find_yamlreel()
FAILURES: "list[str]" = []


def run(args: "list[str]", cwd: Path, env: "dict | None" = None) -> subprocess.CompletedProcess:
    full_env = dict(os.environ)
    full_env.update(env or {})
    return subprocess.run([sys.executable, *args], cwd=str(cwd), capture_output=True, text=True, env=full_env)


def result_of(proc: subprocess.CompletedProcess) -> dict:
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("RESULT ")]
    assert lines, "no RESULT line in stdout:\n%s\n%s" % (proc.stdout, proc.stderr)
    return json.loads(lines[-1][len("RESULT "):])


def case(fn):
    def wrapper(*a, **kw):
        try:
            fn(*a, **kw)
            print("PASS %s" % fn.__name__)
        except Exception:  # noqa: BLE001 - report every failure
            FAILURES.append(fn.__name__)
            print("FAIL %s\n%s" % (fn.__name__, traceback.format_exc()))
    wrapper.__name__ = fn.__name__
    return wrapper


@case
def test_frontmatter() -> None:
    text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    assert m, "SKILL.md has no frontmatter"
    fm = m.group(1)
    name = re.search(r"^name:\s*(\S+)\s*$", fm, re.M)
    desc = re.search(r"^description:\s*(.+)$", fm, re.M)
    assert name and re.fullmatch(r"[a-z0-9-]{1,64}", name.group(1)), "bad name"
    assert desc and len(desc.group(1)) <= 1024, "description missing or too long"
    assert len(text.splitlines()) < 150, "SKILL.md must stay under 150 lines"


@case
def test_hygiene() -> None:
    bad = []
    for p in ROOT.rglob("*"):
        rel = p.relative_to(ROOT)
        if not p.is_file() or rel.parts[0] in (".git", "docs", "yamlreel-output") or "__pycache__" in rel.parts:
            continue
        if p.suffix == ".wav":
            bad.append("%s: wav file" % rel)
        if rel == Path("tests/e2e.py"):
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if re.search(r"profile id", text, re.I):
            bad.append("%s: 'profile id'" % rel)
        if "/Users/" in text:
            bad.append("%s: personal path" % rel)
        if p.suffix == ".yaml" and re.search(r"^\s*watermark:", text, re.M):
            bad.append("%s: watermark" % rel)
        if p.suffix == ".yaml" and re.search(r"\bTODO\b", re.sub(r"(^|\s)#.*$", "", text, flags=re.M)):
            bad.append("%s: TODO" % rel)
    assert not bad, "; ".join(bad)


@case
def test_scene_snippets() -> None:
    assert YAMLREEL, "yamlreel not found"
    text = (ROOT / "references" / "scene-types.md").read_text(encoding="utf-8")
    blocks = re.findall(r"```yaml\n(.*?)```", text, re.S)
    assert len(blocks) == 10, "expected 10 scene snippets, found %d" % len(blocks)
    with tempfile.TemporaryDirectory() as tmp:
        for i, block in enumerate(blocks):
            body = "".join("  " + ln if ln.strip() else ln for ln in block.splitlines(True))
            spec = Path(tmp) / ("snippet%d.yaml" % i)
            spec.write_text("theme: midnight\nformats: [square]\nscenes:\n" + body, encoding="utf-8")
            r = subprocess.run([YAMLREEL, "validate", str(spec)], capture_output=True, text=True, cwd=tmp)
            assert r.returncode == 0, "snippet %d failed: %s" % (i, r.stderr or r.stdout)


GOOD_SPEC = "theme: midnight\nformats: [square]\nscenes:\n  - type: title\n    title: Hello\n    seconds: 1\n"


@case
def test_preflight() -> None:
    with tempfile.TemporaryDirectory() as proj, tempfile.TemporaryDirectory() as elsewhere:
        proj_p, other = Path(proj), Path(elsewhere)

        def spec(name: str, text: str, where: Path = proj_p) -> Path:
            p = where / name
            p.write_text(text, encoding="utf-8")
            return p

        r = run([str(RENDER), str(spec("out.yaml", GOOD_SPEC, other)), "--stage", "preview"], proj_p)
        assert r.returncode == 2, "outside cwd: %d" % r.returncode
        r = run([str(RENDER), str(spec("todo.yaml", GOOD_SPEC.replace("Hello", "TODO fix"))), "--stage", "preview"], proj_p)
        assert r.returncode == 2, "TODO: %d" % r.returncode
        r = run([str(RENDER), str(spec("todo2.yaml", GOOD_SPEC + "# TODO later\n")), "--stage", "preview"], proj_p)
        assert r.returncode != 2, "TODO in comment should pass preflight: %d %s" % (r.returncode, r.stderr)
        secret = GOOD_SPEC.replace("Hello", "sk-" + "a" * 24)
        r = run([str(RENDER), str(spec("secret.yaml", secret)), "--stage", "preview"], proj_p)
        assert r.returncode == 2, "secret: %d" % r.returncode
        good = str(spec("good.yaml", GOOD_SPEC))
        r = run([str(RENDER), good, "--stage", "preview", "--voice-url", "https://api.example.com/mcp/"], proj_p)
        assert r.returncode == 2, "remote voice url: %d" % r.returncode
        r = run([str(RENDER), good, "--stage", "preview", "--voice-url", "http://127.0.0.1:3900/mcp/"], proj_p)
        assert r.returncode != 2, "local voice url must pass preflight (got %d)" % r.returncode
        r = run([str(RENDER), good, "--stage", "preview", "--out", str(other / "o")], proj_p)
        assert r.returncode == 2, "out dir outside cwd: %d" % r.returncode


@case
def test_warning_blocks_final() -> None:
    long_stat = ("theme: midnight\nformats: [square]\nscenes:\n  - type: stat\n"
                 "    value: \"12,345,678,901 requests\"\n    label: x\n    seconds: 2\n")
    with tempfile.TemporaryDirectory() as proj:
        p = Path(proj) / "warn.yaml"
        p.write_text(long_stat, encoding="utf-8")
        r = run([str(RENDER), str(p), "--stage", "all"], Path(proj))
        assert r.returncode == 3, "expected 3, got %d\n%s\n%s" % (r.returncode, r.stdout, r.stderr)
        res = result_of(r)
        assert not res["ok"] and res["warnings"], res
        assert not (Path(proj) / "yamlreel-output" / "warn" / "final").exists(), "final must not run"
        r = run([str(RENDER), str(p), "--stage", "all", "--allow-warnings"], Path(proj))
        assert r.returncode == 0, "allow-warnings: %d\n%s" % (r.returncode, r.stderr)


@case
def test_check_setup() -> None:
    r = run([str(CHECK), "--json"], ROOT)
    data = json.loads(r.stdout)
    assert r.returncode == 0 and data["ok"], r.stdout
    with tempfile.TemporaryDirectory() as empty:
        r = run([str(CHECK), "--json"], ROOT, env={"YAMLREEL_FONT_DIR": empty})
        data = json.loads(r.stdout)
        fonts = [c for c in data["checks"] if c["name"] == "fonts"][0]
        assert r.returncode == 1 and not fonts["ok"] and "font" in fonts["fix"], fonts


def spec_seconds(text: str) -> float:
    return sum(float(x) for x in re.findall(r"^\s*(?:-\s+)?seconds:\s*([\d.]+)\s*$", text, re.M))


def title_of(text: str) -> str:
    return re.search(r"^\s*title:\s*(.+?)\s*$", text.split("scenes:")[0], re.M).group(1).strip("\"'")


def example_test(example: Path, preview_only: bool) -> None:
    text = example.read_text(encoding="utf-8")
    expected = spec_seconds(text)
    stage = "preview" if preview_only else "all"
    with tempfile.TemporaryDirectory() as proj:
        out = Path(proj) / example.stem
        r = run([str(RENDER), str(example), "--stage", stage, "--out", str(out)], Path(proj))
        assert r.returncode == 0, "exit %d\n%s\n%s" % (r.returncode, r.stdout, r.stderr)
        res = result_of(r)
        assert res["ok"] and res["warnings"] == [], res
        assert res["formats"], "no formats rendered"
        for fmt, info in res["formats"].items():
            video = Path(info["video"])
            assert video.stat().st_size > 50 * 1024, "%s video too small" % fmt
            assert Path(info["poster"]).is_file() and Path(info["contact"]).is_file(), fmt
            assert abs(info["seconds"] - expected) <= 0.1 * expected, "%s: %.1fs vs %.1fs" % (fmt, info["seconds"], expected)
        share = Path(res["share_copy"]).read_text(encoding="utf-8")
        assert title_of(text) in share, "share-copy lacks the title"
        assert (out / "render-log.txt").is_file()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true", help="examples: preview stage only")
    args = ap.parse_args()
    if not YAMLREEL:
        print("yamlreel not found; install it (scripts/check_setup.py --install)")
        return 1
    test_frontmatter()
    test_hygiene()
    test_scene_snippets()
    test_preflight()
    test_warning_blocks_final()
    test_check_setup()
    for ex in sorted((ROOT / "examples").glob("*.yaml")):
        name = "example_%s" % ex.stem

        @case
        def run_example(ex=ex):
            example_test(ex, args.preview)
        run_example.__name__ = name
        print("-- %s" % name)
        run_example()
    print("\n%d failure(s)" % len(FAILURES) if FAILURES else "\nall passed")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
