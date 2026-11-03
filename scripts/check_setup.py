#!/usr/bin/env python3
"""Check (and optionally install) what the yamlreel-video skill needs.

Usage: check_setup.py [--install] [--json]

Stdlib only. Runs on Python 3.8+ so it can report "Python too old" instead of crashing.
Exit 0 when every check passes, 1 otherwise.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import NamedTuple

MIN_PY = (3, 10)
# The yamlreel version this skill needs. The single source of truth: --install, the version check, SKILL.md,
# README.md (tests/e2e.py asserts both quote VERSION_SPEC) and CI all derive from these two constants.
# TODO-RELEASE: placeholder until the yamlreel release that ships `story`, --contact-frames, table/array/cta,
# stagger/count, transition/energy and music styles is out. Set the real range here, then switch CI's
# YAMLREEL_SPEC to the PyPI pin and update the two doc strings.
MIN_VERSION = (0, 3, 0)
MAX_EXCLUSIVE = (0, 4, 0)
VERSION_SPEC = ">=%s,<%d.%d" % (".".join(map(str, MIN_VERSION)), MAX_EXCLUSIVE[0], MAX_EXCLUSIVE[1])
PIN = "yamlreel[ffmpeg]" + VERSION_SPEC
# Optional pip requirement override (CI installs yamlreel main from git until the release is on PyPI).
SPEC_ENV = "YAMLREEL_SPEC"
UPGRADE_MSG = ("this skill needs a yamlreel with `story` and `render --contact-frames` (%s); upgrade yamlreel: "
               "pip install --upgrade \"%s\"" % (VERSION_SPEC, PIN))
FONTS = ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf", "DejaVuSansMono.ttf")
PY_CANDIDATES = ("python3.13", "python3.12", "python3.11", "python3.10", "python3")
SMOKE_SPEC = "theme: midnight\nformats: [square]\nscenes:\n  - type: title\n    title: Setup check\n    seconds: 1\n"
# Validated (not rendered) by probe_features: every feature the skill's references rely on that older builds lack.
PROBE_SPEC = """theme: midnight
formats: [square]
music: {style: lofi, seed: 7}
scenes:
  - type: table
    columns: [id, name]
    rows:
      - [1, Ada]
      - [2, Lin]
    stagger: 0.4
    energy: mid
    transition: fade
    seconds: 3
  - type: array
    items: [a, b]
    steps:
      - {at: 1.0, push: c}
    seconds: 3
  - type: cta
    question: Which one?
    answers: [A, B]
    transition: slide
    seconds: 3
"""


def default_venv() -> Path:
    return Path(os.environ.get("YAMLREEL_VENV") or Path.home() / ".yamlreel" / "venv")


def venv_bin(venv: Path, name: str) -> Path:
    return venv / ("Scripts" if os.name == "nt" else "bin") / name


def candidates() -> "list[str]":
    """Existing yamlreel binaries in priority order: $YAMLREEL_BIN, the skill venv, then PATH."""
    found: "list[str]" = []
    env = os.environ.get("YAMLREEL_BIN")
    paths = [env] if env else []
    paths.append(str(venv_bin(default_venv(), "yamlreel")))
    on_path = shutil.which("yamlreel")
    if on_path:
        paths.append(on_path)
    for c in paths:
        if c not in found and Path(c).exists():
            found.append(c)
    return found


def find_yamlreel() -> "str | None":
    """The first candidate that is a usable yamlreel (right version, has the features); others are skipped.

    render.py and check_setup.py both call this, so the binary the setup check approves is the one that renders.
    """
    for c in candidates():
        if assess(c).usable:
            return c
    return None


def same_file(a: str, b: str) -> bool:
    try:
        return os.path.samefile(a, b)
    except OSError:
        return a == b


def find_python() -> "str | None":
    """First interpreter on PATH that is Python >= MIN_PY."""
    probe = "import sys; sys.exit(0 if sys.version_info >= %r else 1)" % (MIN_PY,)
    for name in PY_CANDIDATES:
        path = shutil.which(name)
        if not path:
            continue
        try:
            if subprocess.run([path, "-c", probe], capture_output=True, timeout=20).returncode == 0:
                return path
        except (OSError, subprocess.SubprocessError):
            continue
    return None


def parse_version(text: str) -> "tuple | None":
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", text)
    return tuple(int(x) for x in m.groups()) if m else None


def font_dirs() -> "list[Path]":
    home = Path.home()
    dirs = [Path("/Library/Fonts"), home / "Library" / "Fonts", Path("/usr/share/fonts"), home / ".local" / "share" / "fonts"]
    env = os.environ.get("YAMLREEL_FONT_DIR")
    # $YAMLREEL_FONT_DIR is searched first, then the system folders.
    return ([Path(env)] if env else []) + dirs


def find_fonts() -> "tuple[list[str], list[str]]":
    """Return (found, missing) font file names."""
    seen = set()
    for d in font_dirs():
        if not d.is_dir():
            continue
        for _root, _dirs, files in os.walk(str(d)):
            seen.update(files)
    found = [f for f in FONTS if f in seen]
    return found, [f for f in FONTS if f not in seen]


def font_fix() -> str:
    if platform.system() == "Darwin":
        return "brew install --cask font-dejavu"
    return "sudo apt install fonts-dejavu-core   (or set font_dir in ~/.config/yamlreel/config.yaml)"


def venv_ffmpeg(yamlreel: str) -> "str | None":
    py = Path(yamlreel).resolve().parent / ("python.exe" if os.name == "nt" else "python")
    if not py.exists():
        return None
    code = "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"
    try:
        r = subprocess.run([str(py), "-c", code], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    out = r.stdout.strip()
    return out if r.returncode == 0 and out and Path(out).exists() else None


def check(name: str, ok: bool, detail: str, fix: str = "") -> dict:
    return {"name": name, "ok": ok, "detail": detail, "fix": fix}


def probe_features(ym: str) -> "tuple[bool, str]":
    """Does this yamlreel have what the skill uses? `story` exists and `render` has --contact-frames."""
    try:
        story = subprocess.run([ym, "story", "--help"], capture_output=True, text=True, timeout=60)
        render = subprocess.run([ym, "render", "--help"], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as e:
        return False, "cannot probe %s: %s" % (ym, e)
    missing = []
    if story.returncode != 0:
        missing.append("`story` command")
    if "--contact-frames" not in render.stdout + render.stderr:
        missing.append("`render --contact-frames`")
    if missing:
        return False, "missing %s" % " and ".join(missing)
    with tempfile.TemporaryDirectory(prefix="yamlreel-probe-") as tmp:
        spec = Path(tmp) / "probe.yaml"
        spec.write_text(PROBE_SPEC, encoding="utf-8")
        try:
            v = subprocess.run([ym, "validate", str(spec)], capture_output=True, text=True, timeout=60, cwd=tmp)
        except (OSError, subprocess.SubprocessError) as e:
            return False, "cannot probe %s: %s" % (ym, e)
    if v.returncode != 0:
        lines = (v.stderr or v.stdout).strip().splitlines()
        return False, "cannot validate a spec using table, array, cta, stagger, transition, energy and music lofi: %s" % (
            lines[-1] if lines else "exit %d" % v.returncode)
    return True, "`story`, `render --contact-frames` and the newer scene types present"


class Assessment(NamedTuple):
    usable: bool
    runs: bool
    text: str
    feat_ok: bool
    feat_detail: str
    unreleased: bool
    error: str


def assess(ym: str) -> Assessment:
    """Version in range (or an unreleased build older than MIN_VERSION that has the features) and features present."""
    try:
        r = subprocess.run([ym, "--version"], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as e:
        return Assessment(False, False, "", False, "version unknown", False, "cannot run %s: %s" % (ym, e))
    text = (r.stdout + r.stderr).strip()
    ver = parse_version(text)
    runs = r.returncode == 0 and ver is not None
    if not runs:
        return Assessment(False, False, text, False, "version unknown", False, "")
    in_range = MIN_VERSION <= ver < MAX_EXCLUSIVE
    feat_ok, feat_detail = probe_features(ym)
    # Features are what matter: a main-branch build that still reports an older number but has them passes.
    unreleased = feat_ok and ver < MIN_VERSION
    return Assessment(feat_ok and (in_range or unreleased), True, text, feat_ok, feat_detail, unreleased, "")


def resolution_check(ym: str) -> "dict | None":
    """Fail when render.py (find_yamlreel) would run a different binary than the one just approved."""
    resolved = find_yamlreel()
    if resolved and same_file(resolved, ym):
        return None
    return check("resolution", False,
                 "checked %s but render.py would run %s" % (ym, resolved or "nothing"),
                 "unset $YAMLREEL_BIN or point it at the checked binary (order: $YAMLREEL_BIN, skill venv, PATH)")


def downgrade_when_smoke_passes(checks: "list[dict]") -> None:
    """The smoke render is authoritative: if it passed, font/ffmpeg pre-check misses are warnings, not failures."""
    smoke = [c for c in checks if c["name"] == "smoke-render"]
    if not smoke or not smoke[0]["ok"]:
        return
    for c in checks:
        if c["name"] in ("fonts", "ffmpeg") and not c["ok"]:
            c["ok"] = True
            c["warning"] = True
            c["detail"] = "warning: %s (the smoke render still passed)" % c["detail"]


def run_checks(preferred: "str | None" = None) -> "tuple[list[dict], str | None]":
    checks: "list[dict]" = []
    py = find_python()
    checks.append(check("python", py is not None, py or "no Python >= 3.10 found on PATH",
                        "brew install python@3.12   (macOS) or sudo apt install python3 python3-venv   (Debian/Ubuntu)"))
    venv = default_venv()
    # When nothing is usable, still diagnose the first binary found so the failing check explains why.
    ym = preferred or find_yamlreel() or next(iter(candidates()), None)
    install_fix = "python3 scripts/check_setup.py --install"
    checks.append(check("venv", venv.is_dir() or (ym is not None and shutil.which("yamlreel") == ym) or bool(os.environ.get("YAMLREEL_BIN")),
                        str(venv) if venv.is_dir() else "no skill venv (fine if yamlreel is on PATH or YAMLREEL_BIN is set)",
                        install_fix))
    usable = False
    if ym:
        a = assess(ym)
        usable = a.usable
        if a.error:
            checks.append(check("yamlreel", False, a.error, install_fix))
        else:
            checks.append(check("features", a.feat_ok, a.feat_detail, UPGRADE_MSG))
            detail = "%s at %s" % (a.text or "unknown version", ym)
            if a.unreleased:
                detail += " (unreleased build: older than %s but has the required features)" % VERSION_SPEC
            checks.append(check("yamlreel", usable, detail, UPGRADE_MSG + "   or: " + install_fix))
    else:
        checks.append(check("yamlreel", False, "no usable yamlreel found (looked at $YAMLREEL_BIN, %s, PATH)" % venv_bin(venv, "yamlreel"), install_fix))

    ff = shutil.which("ffmpeg") or (venv_ffmpeg(ym) if ym else None)
    checks.append(check("ffmpeg", ff is not None, ff or "ffmpeg not found",
                        'pip install "yamlreel[ffmpeg]"  into the yamlreel venv, or install ffmpeg with your package manager'))
    found, missing = find_fonts()
    checks.append(check("fonts", not missing, "found %s" % ", ".join(found) if not missing else "missing %s" % ", ".join(missing),
                        font_fix() + "   (the skill never installs fonts itself)"))
    if ym and usable:
        checks.append(smoke_render(ym))
        mismatch = resolution_check(ym)
        if mismatch:
            checks.append(mismatch)
    else:
        checks.append(check("smoke-render", False, "skipped: yamlreel is not usable", install_fix))
    downgrade_when_smoke_passes(checks)
    return checks, ym


def smoke_render(ym: str) -> dict:
    """Authoritative: exercises yamlreel's own font and ffmpeg lookup."""
    with tempfile.TemporaryDirectory(prefix="yamlreel-smoke-") as tmp:
        spec = Path(tmp) / "smoke.yaml"
        spec.write_text(SMOKE_SPEC, encoding="utf-8")
        cmd = [ym, "render", str(spec), "--preview", "--no-voice", "--music", "none", "--format", "square",
               "--out", str(Path(tmp) / "out")]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=tmp)
        except (OSError, subprocess.SubprocessError) as e:
            return check("smoke-render", False, str(e), "check the other failures above")
        video = Path(tmp) / "out" / "square" / "video.mp4"
        if r.returncode == 0 and video.is_file() and video.stat().st_size > 0:
            return check("smoke-render", True, "1s title scene rendered")
        err = (r.stderr or r.stdout).strip().splitlines()
        msg = err[-1] if err else "render failed (exit %d)" % r.returncode
        fix = "see references/troubleshooting.md"
        if "font" in msg.lower():
            fix = "install DejaVu fonts (%s) or set font_dir in ~/.config/yamlreel/config.yaml" % font_fix()
        elif "ffmpeg" in msg.lower():
            fix = 'pip install "yamlreel[ffmpeg]" into the yamlreel venv, or install ffmpeg'
        return check("smoke-render", False, msg, fix)


def venv_python_ok(venv: Path) -> bool:
    """True when the venv's interpreter exists and is >= MIN_PY."""
    py = venv_bin(venv, "python")
    if not py.exists():
        return False
    probe = "import sys; sys.exit(0 if sys.version_info >= %r else 1)" % (MIN_PY,)
    try:
        return subprocess.run([str(py), "-c", probe], capture_output=True, timeout=30).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def install(log) -> "tuple[int, str | None]":
    """Create/refresh the venv and install yamlreel. Returns (exit code, venv yamlreel path).

    Progress goes through `log` and child output to stderr so `--install --json` keeps stdout pure JSON.
    """
    py = find_python()
    if not py:
        log("fail python: no Python >= 3.10 found [fix: brew install python@3.12 or sudo apt install python3 python3-venv]")
        return 1, None
    venv = default_venv()
    override = os.environ.get(SPEC_ENV)
    requirement = override or PIN
    if override:
        log("%s is set: installing %r instead of the pinned %r" % (SPEC_ENV, override, PIN))
    try:
        if venv_bin(venv, "python").exists() and not venv_python_ok(venv):
            if venv != Path.home() / ".yamlreel" / "venv":
                log("install failed: %s has an old Python and is not the default skill venv (%s); "
                    "not recreating it. Move it away or unset YAMLREEL_VENV." % (venv, Path.home() / ".yamlreel" / "venv"))
                return 1, None
            if (venv / "pyvenv.cfg").is_file():
                log("venv %s uses Python < 3.10; recreating it" % venv)
                shutil.rmtree(str(venv))
            else:
                log("install failed: %s has an old Python but is not a venv; move it away" % venv)
                return 1, None
        if not venv_bin(venv, "python").exists():
            log("creating venv %s with %s" % (venv, py))
            venv.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run([py, "-m", "venv", str(venv)], check=True, stdout=sys.stderr)
        log("installing %s" % requirement)
        subprocess.run([str(venv_bin(venv, "python")), "-m", "pip", "install", "--upgrade", requirement],
                       check=True, stdout=sys.stderr)
    except (OSError, subprocess.CalledProcessError) as e:
        log("install failed: %s" % e)
        return 1, None
    log("installed. Fonts and system packages are never installed by this script.")
    cand = venv_bin(venv, "yamlreel")
    return 0, str(cand) if cand.exists() else None


def main(argv: "list[str] | None" = None) -> int:
    ap = argparse.ArgumentParser(description="Check the yamlreel-video skill environment.")
    ap.add_argument("--install", action="store_true", help="create the venv and pip install yamlreel (asks nothing; run only with the user's yes)")
    ap.add_argument("--json", action="store_true", help="machine-readable output (stdout is a single JSON object)")
    args = ap.parse_args(argv)
    if sys.version_info < (3, 8):
        print("fail python: this script needs Python 3.8+ to run")
        return 1
    preferred = None
    if args.install:
        # With --json, progress is sent to stderr so stdout stays valid JSON.
        log = (lambda m: print(m, file=sys.stderr)) if args.json else print
        rc, preferred = install(log)
        if rc:
            if args.json:
                print(json.dumps({"ok": False, "checks": [check("install", False, "install failed (see stderr)", "")],
                                  "yamlreel": None}))
            return rc
    checks, ym = run_checks(preferred)
    ok = all(c["ok"] for c in checks)
    if args.json:
        print(json.dumps({"ok": ok, "checks": checks, "yamlreel": ym}))
    else:
        for c in checks:
            status = "warn" if c.get("warning") else ("ok  " if c["ok"] else "fail")
            line = "%s %s: %s" % (status, c["name"], c["detail"])
            if c["fix"] and (not c["ok"] or c.get("warning")):
                line += " [fix: %s]" % c["fix"]
            print(line)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
