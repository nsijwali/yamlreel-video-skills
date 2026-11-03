#!/usr/bin/env python3
"""Preflight, validate, preview, check the contact sheet, then render a yamlreel spec.

Usage: render.py SPEC [--stage preview|final|all] [--out DIR] [--format F] [--contact-frames N]
                      [--voice-url URL] [--allow-warnings]

Stdlib only. Exit codes: 0 ok, 1 yamlreel error/timeout/OS error, 2 preflight refused, 3 warnings block the final
render, 4 usage error (bad arguments). The last stdout line is `RESULT {json}`, also on refusals and usage errors.
Default output folder: <spec folder>/out. $YAMLREEL_RENDER_TIMEOUT (seconds) overrides every subprocess timeout.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import struct
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, urlunparse

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
from check_setup import find_yamlreel  # noqa: E402

EXAMPLES_DIR = (SCRIPTS_DIR.parent / "examples").resolve()
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
FORMATS = ("vertical", "landscape", "square")
PNG_SIG = b"\x89PNG\r\n\x1a\n"

SECRET_PATTERNS = (
    ("AWS access key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("API secret key (sk-...)", re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{20,}")),
    ("GitHub token", re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}|github_pat_")),
    ("Google API key", re.compile(r"AIza[0-9A-Za-z_-]{35}")),
    ("Stripe live key", re.compile(r"[sr]k_live_[0-9a-zA-Z]{16,}")),
    ("GitLab token", re.compile(r"glpat-")),
    ("Slack token", re.compile(r"xox[abposr]-")),
    ("JWT", re.compile(r"eyJ[\w-]+\.eyJ[\w-]+")),
    ("private key block", re.compile(r"-----BEGIN")),
    # An assignment-looking value is required so narration prose ("the token: refresh it") is not flagged:
    # a quoted value of 6+ chars, or a bare value of 8+ chars holding a digit or one of _ - / + =.
    ("password/secret/token/api key assignment", re.compile(
        r"""(?:password|passwd|secret|token|api[_-]?key)["']?\s*[:=]\s*"""
        r"""(?:"[^"\s]{6,}"|'[^'\s]{6,}'|(?=[^\s"']*[0-9_\-/+=])[^\s"']{8,})""", re.I)),
)
COMMENT_RE = re.compile(r"(^|\s)#.*$")
TODO_RE = re.compile(r"\bTODO\b")
RENDERED_RE = re.compile(r"^\s+(\w+): (.+) \(([\d.]+)s, (\d+)x(\d+)\)\s*$")
WARNING_RE = re.compile(r"^\s*warning: (.*)$")
SHARE_RE = re.compile(r"^share copy: (.+)$")


class Refused(Exception):
    """Preflight refusal (exit 2)."""


def inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def redact_url(url: str) -> str:
    """Drop userinfo (user:password@) from a URL so it can be logged."""
    try:
        u = urlparse(url)
        if u.username is None and u.password is None:
            return url
        host = u.netloc.rsplit("@", 1)[-1]
        return urlunparse(u._replace(netloc=host))
    except ValueError:
        return "<unparseable url>"


def userinfo_of(url: str) -> "str | None":
    try:
        u = urlparse(url)
    except ValueError:
        return None
    return u.netloc.rsplit("@", 1)[0] if "@" in u.netloc else None


def preflight(spec: Path, out: Path, voice_url: "str | None", cwd: Path) -> None:
    spec, out, cwd = spec.resolve(), out.resolve(), cwd.resolve()
    if cwd == Path("/") or cwd == Path.home().resolve():
        raise Refused("current directory %s is your home or the filesystem root; cd into the project folder first" % cwd)
    if not spec.is_file():
        raise Refused("spec not found: %s" % spec)
    if not (inside(spec, cwd) or inside(spec, EXAMPLES_DIR)):
        raise Refused("spec %s is outside the current directory %s; move it into the project folder" % (spec, cwd))
    if not inside(out, cwd):
        raise Refused("output folder %s is outside the current directory %s" % (out, cwd))
    try:
        text = spec.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise Refused("cannot read spec: %s" % e)
    for n, line in enumerate(text.splitlines(), 1):
        if TODO_RE.search(COMMENT_RE.sub("", line)):
            raise Refused("TODO placeholder at %s:%d; fill it in: %s" % (spec.name, n, line.strip()))
    for n, line in enumerate(text.splitlines(), 1):
        for label, rx in SECRET_PATTERNS:
            if rx.search(line):
                raise Refused("possible secret (%s) at %s:%d; specs are burned into frames and share copy. "
                              "Use a placeholder or rename the token." % (label, spec.name, n))
    if voice_url is not None:
        shown = redact_url(voice_url) if "\\" not in voice_url else "<url with backslash>"
        msg = ("--voice-url must be http(s) on 127.0.0.1, localhost or ::1 (narration text is sent there); got %s" % shown)
        if any(c.isspace() or c == "\\" or ord(c) < 32 for c in voice_url):
            raise Refused(msg)
        try:
            u = urlparse(voice_url)
            u.port  # noqa: B018 - raises ValueError on a bad port
        except ValueError:
            raise Refused(msg)
        if u.scheme not in ("http", "https") or (u.hostname or "") not in LOCAL_HOSTS:
            raise Refused(msg)


class Logger:
    def __init__(self, path: "Path | None", redactions: "list[str] | None" = None) -> None:
        self.path = path
        self.redactions = [r for r in (redactions or []) if r]

    def write(self, text: str) -> None:
        for secret in self.redactions:
            text = text.replace(secret, "***")
        if self.path is not None:
            try:
                with self.path.open("a", encoding="utf-8") as f:
                    f.write(text)
            except OSError:
                pass  # the log is best effort; never fail a render because of it


def timeout_for(default: int) -> int:
    try:
        return int(os.environ["YAMLREEL_RENDER_TIMEOUT"])
    except (KeyError, ValueError):
        return default


def run_yamlreel(cmd: "list[str]", log: Logger, timeout: int = 3600) -> "subprocess.CompletedProcess":
    """Run yamlreel. A timeout or OS error becomes a failed CompletedProcess (returncode 1) so callers exit 1."""
    shown = list(cmd)
    for i, part in enumerate(shown[:-1]):
        if part == "--voice-url":
            shown[i + 1] = redact_url(shown[i + 1])
    log.write("[%s] $ %s\n" % (datetime.now().isoformat(timespec="seconds"), " ".join(shown)))
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_for(timeout))
    except subprocess.TimeoutExpired:
        r = subprocess.CompletedProcess(cmd, 1, "", "yamlreel timed out after %ds" % timeout_for(timeout))
    except OSError as e:
        r = subprocess.CompletedProcess(cmd, 1, "", "cannot run yamlreel: %s" % e)
    log.write("exit %d\n" % r.returncode)
    if r.stdout:
        log.write("stdout:\n%s\n" % r.stdout)
    if r.stderr:
        log.write("stderr:\n%s\n" % r.stderr)
    return r


def png_size(path: Path) -> "tuple[int, int] | None":
    try:
        with path.open("rb") as f:
            head = f.read(24)
    except OSError:
        return None
    if len(head) < 24 or head[:8] != PNG_SIG or head[12:16] != b"IHDR":
        return None
    w, h = struct.unpack(">II", head[16:24])
    return (w, h) if w and h else None


def parse_render(stdout: str, stderr: str) -> "tuple[dict, list[str], str | None]":
    formats: dict = {}
    for line in stdout.splitlines():
        m = RENDERED_RE.match(line)
        if m and m.group(1) in FORMATS:
            video = Path(m.group(2)).resolve()
            folder = video.parent
            formats[m.group(1)] = {
                "video": str(video),
                "poster": str(folder / "poster.jpg"),
                "contact": str(folder / "contact.png"),
                "seconds": float(m.group(3)),
                "size": [int(m.group(4)), int(m.group(5))],
            }
    warnings = [m.group(1) for m in (WARNING_RE.match(x) for x in stderr.splitlines()) if m]
    share = None
    for line in stdout.splitlines():
        m = SHARE_RE.match(line)
        if m:
            share = str(Path(m.group(1)).resolve())
    return formats, warnings, share


def build_cmd(ym: str, sub: str, spec: Path, args: argparse.Namespace, out: "Path | None" = None,
              preview: bool = False) -> "list[str]":
    cmd = [ym, sub, str(spec)]
    if sub == "render":
        cmd += ["--out", str(out)]
        if preview:
            cmd.append("--preview")
        if args.voice_url:
            cmd += ["--voice-url", args.voice_url]
        else:
            cmd.append("--no-voice")
        if args.format:
            cmd += ["--format", args.format]
        if args.contact_frames is not None:
            cmd += ["--contact-frames", str(args.contact_frames)]
    return cmd


def result_line(stage: str, ok: bool, warnings: "list[str]", formats: dict, share: "str | None") -> str:
    return "RESULT " + json.dumps({"stage": stage, "ok": ok, "warnings": warnings, "formats": formats,
                                   "share_copy": share})


def do_render(ym: str, spec: Path, args: argparse.Namespace, out: Path, preview: bool, log: Logger):
    """Return (returncode, formats, warnings, share, stderr)."""
    label = "preview" if preview else "final"
    print("render %s ..." % label, flush=True)
    r = run_yamlreel(build_cmd(ym, "render", spec, args, out=out, preview=preview), log,
                     timeout=1800 if preview else 3600)
    if r.returncode != 0:
        sys.stderr.write(r.stderr)
        return r.returncode, {}, [], None, r.stderr
    formats, warnings, share = parse_render(r.stdout, r.stderr)
    for fmt, info in formats.items():
        print("  %s: %s (%.1fs, %dx%d)" % (fmt, info["video"], info["seconds"], *info["size"]))
    for w in warnings:
        print("  warning: %s" % w)
    return 0, formats, warnings, share, r.stderr


class UsageError(Exception):
    """Bad command-line arguments (exit 4)."""


class Parser(argparse.ArgumentParser):
    def error(self, message: str):  # type: ignore[override]
        raise UsageError(message)


def main(argv: "list[str] | None" = None) -> int:
    ap = Parser(description="Validate, preview and render a yamlreel spec.")
    ap.add_argument("spec")
    ap.add_argument("--stage", choices=("preview", "final", "all"), default="all")
    ap.add_argument("--out", help="output folder (default <spec folder>/out)")
    ap.add_argument("--format", choices=FORMATS, help="render only this format")
    ap.add_argument("--contact-frames", type=int, default=None, help="stills per scene on the contact sheet (1-8; preview default 3)")
    ap.add_argument("--voice-url", help="LOCAL text-to-speech server; without it every render uses --no-voice")
    ap.add_argument("--allow-warnings", action="store_true", help="do not stop before the final render on preview warnings")
    try:
        args = ap.parse_args(argv)
        if args.contact_frames is not None and not 1 <= args.contact_frames <= 8:
            raise UsageError("--contact-frames must be between 1 and 8, got %d" % args.contact_frames)
    except UsageError as e:
        print("usage error: %s" % e, file=sys.stderr)
        print(result_line("usage", False, ["usage error: %s" % e], {}, None))
        return 4
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)

    cwd = Path.cwd()
    spec = Path(args.spec).resolve()
    out = Path(args.out).resolve() if args.out else (spec.parent / "out").resolve()
    try:
        preflight(spec, out, args.voice_url, cwd)
    except Refused as e:
        print("refused: %s" % e, file=sys.stderr)
        print(result_line(args.stage, False, ["preflight: %s" % e], {}, None))
        return 2

    ym = find_yamlreel()
    if not ym:
        print("error: yamlreel not found; run scripts/check_setup.py", file=sys.stderr)
        print(result_line(args.stage, False, ["yamlreel not found"], {}, None))
        return 1

    try:
        out.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        msg = "cannot create output folder %s: %s" % (out, e)
        print("error: %s" % msg, file=sys.stderr)
        print(result_line(args.stage, False, [msg], {}, None))
        return 1
    log = Logger(out / "render-log.txt", [userinfo_of(args.voice_url)] if args.voice_url else None)

    print("validate ...", flush=True)
    r = run_yamlreel(build_cmd(ym, "validate", spec, args), log, timeout=120)
    if r.returncode != 0:
        sys.stderr.write(r.stderr)
        print(result_line(args.stage, False, [r.stderr.strip()], {}, None))
        return 1
    print(r.stdout.strip())

    formats: dict = {}
    warnings: "list[str]" = []
    share = None
    stage_done = args.stage

    if args.stage in ("preview", "all"):
        pargs = argparse.Namespace(**vars(args))
        if pargs.contact_frames is None:
            pargs.contact_frames = 3
        rc, formats, warnings, share, stderr = do_render(ym, spec, pargs, out / "preview", True, log)
        if rc != 0:
            print(result_line("preview", False, [stderr.strip()], {}, None))
            return 1
        if not formats:
            msg = "yamlreel printed no rendered formats"
            print("error: %s" % msg, file=sys.stderr)
            print(result_line("preview", False, [msg], {}, None))
            return 1
        for fmt, info in formats.items():
            size = png_size(Path(info["contact"]))
            if size is None:
                msg = "%s: contact sheet %s is missing or not a valid PNG" % (fmt, info["contact"])
                print("error: %s" % msg, file=sys.stderr)
                print(result_line("preview", False, warnings + [msg], formats, share))
                return 1
            print("  contact sheet ok: %s (%dx%d)" % (info["contact"], *size))
        if warnings and not args.allow_warnings:
            print("stopping: preview produced warnings. Shorten text or reorder `at` cues, or pass --allow-warnings.",
                  file=sys.stderr)
            print(result_line("preview", False, warnings, formats, share))
            return 3
        stage_done = "preview"

    if args.stage in ("final", "all"):
        rc, formats, warnings, share, stderr = do_render(ym, spec, args, out / "final", False, log)
        if rc != 0:
            print(result_line("final", False, [stderr.strip()], {}, None))
            return 1
        stage_done = "final"

    if share:
        print("share copy: %s" % share)
    print(result_line(stage_done, True, warnings, formats, share))
    return 0


if __name__ == "__main__":
    sys.exit(main())
