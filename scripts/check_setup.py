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

MIN_PY = (3, 10)
MIN_YAMLREEL = (0, 2, 2)
MAX_YAMLREEL_EXCL = (0, 3, 0)
PIN = "yamlreel[ffmpeg]>=0.2.2,<0.3"
FONTS = ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf", "DejaVuSansMono.ttf")
PY_CANDIDATES = ("python3.13", "python3.12", "python3.11", "python3.10", "python3")
SMOKE_SPEC = "theme: midnight\nformats: [square]\nscenes:\n  - type: title\n    title: Setup check\n    seconds: 1\n"


def default_venv() -> Path:
    return Path(os.environ.get("YAMLREEL_VENV") or Path.home() / ".yamlreel" / "venv")


def venv_bin(venv: Path, name: str) -> Path:
    return venv / ("Scripts" if os.name == "nt" else "bin") / name


def find_yamlreel() -> "str | None":
    """$YAMLREEL_BIN, then PATH, then the skill venv."""
    env = os.environ.get("YAMLREEL_BIN")
    if env:
        return env if Path(env).exists() else None
    on_path = shutil.which("yamlreel")
    if on_path:
        return on_path
    cand = venv_bin(default_venv(), "yamlreel")
    return str(cand) if cand.exists() else None


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
    if env is not None:
        # An explicit value (even an empty folder) replaces the defaults.
        return [Path(env)] if env else []
    return dirs


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
    py = Path(yamlreel).parent / ("python.exe" if os.name == "nt" else "python")
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
    return {"name": name, "ok": ok, "detail": detail, "fix": "" if ok else fix}


def run_checks() -> "tuple[list[dict], str | None]":
    checks: "list[dict]" = []
    py = find_python()
    checks.append(check("python", py is not None, py or "no Python >= 3.10 found on PATH",
                        "brew install python@3.12   (macOS) or sudo apt install python3 python3-venv   (Debian/Ubuntu)"))
    venv = default_venv()
    ym = find_yamlreel()
    install_fix = "python3 scripts/check_setup.py --install"
    checks.append(check("venv", venv.is_dir() or (ym is not None and shutil.which("yamlreel") == ym) or bool(os.environ.get("YAMLREEL_BIN")),
                        str(venv) if venv.is_dir() else "no skill venv (fine if yamlreel is on PATH or YAMLREEL_BIN is set)",
                        install_fix))
    version_ok = False
    if ym:
        try:
            r = subprocess.run([ym, "--version"], capture_output=True, text=True, timeout=60)
            text = (r.stdout + r.stderr).strip()
            ver = parse_version(text)
            version_ok = r.returncode == 0 and ver is not None and MIN_YAMLREEL <= ver < MAX_YAMLREEL_EXCL
            checks.append(check("yamlreel", version_ok, "%s at %s" % (text or "unknown version", ym),
                                'pip install --upgrade "%s"   or: %s' % (PIN, install_fix)))
        except (OSError, subprocess.SubprocessError) as e:
            checks.append(check("yamlreel", False, "cannot run %s: %s" % (ym, e), install_fix))
    else:
        checks.append(check("yamlreel", False, "yamlreel not found (looked at $YAMLREEL_BIN, PATH, %s)" % venv_bin(venv, "yamlreel"), install_fix))

    ff = shutil.which("ffmpeg") or (venv_ffmpeg(ym) if ym else None)
    checks.append(check("ffmpeg", ff is not None, ff or "ffmpeg not found",
                        'pip install "imageio-ffmpeg"  into the yamlreel venv, or install ffmpeg with your package manager'))
    found, missing = find_fonts()
    checks.append(check("fonts", not missing, "found %s" % ", ".join(found) if not missing else "missing %s" % ", ".join(missing),
                        font_fix() + "   (the skill never installs fonts itself)"))
    if ym and version_ok:
        checks.append(smoke_render(ym))
    else:
        checks.append(check("smoke-render", False, "skipped: yamlreel is not usable", install_fix))
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
            fix = 'pip install "imageio-ffmpeg" into the yamlreel venv, or install ffmpeg'
        return check("smoke-render", False, msg, fix)


def install() -> int:
    py = find_python()
    if not py:
        print("fail python: no Python >= 3.10 found [fix: brew install python@3.12 or sudo apt install python3 python3-venv]")
        return 1
    venv = default_venv()
    try:
        if not venv_bin(venv, "python").exists():
            print("creating venv %s with %s" % (venv, py))
            venv.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run([py, "-m", "venv", str(venv)], check=True)
        print("installing %s" % PIN)
        subprocess.run([str(venv_bin(venv, "python")), "-m", "pip", "install", "--upgrade", PIN], check=True)
    except (OSError, subprocess.CalledProcessError) as e:
        print("install failed: %s" % e)
        return 1
    print("installed. Fonts and system packages are never installed by this script.")
    return 0


def main(argv: "list[str] | None" = None) -> int:
    ap = argparse.ArgumentParser(description="Check the yamlreel-video skill environment.")
    ap.add_argument("--install", action="store_true", help="create the venv and pip install yamlreel (asks nothing; run only with the user's yes)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)
    if sys.version_info < (3, 8):
        print("fail python: this script needs Python 3.8+ to run")
        return 1
    if args.install:
        rc = install()
        if rc:
            return rc
    checks, ym = run_checks()
    ok = all(c["ok"] for c in checks)
    if args.json:
        print(json.dumps({"ok": ok, "checks": checks, "yamlreel": ym}))
    else:
        for c in checks:
            line = "%s %s: %s" % ("ok  " if c["ok"] else "fail", c["name"], c["detail"])
            if c["fix"]:
                line += " [fix: %s]" % c["fix"]
            print(line)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
