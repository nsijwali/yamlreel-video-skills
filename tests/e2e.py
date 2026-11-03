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
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
from check_setup import VERSION_SPEC, find_yamlreel  # noqa: E402
import check_setup  # noqa: E402
import render as render_mod  # noqa: E402

RENDER = SCRIPTS / "render.py"
CHECK = SCRIPTS / "check_setup.py"
YAMLREEL = find_yamlreel()
FAILURES: "list[str]" = []


def run(args: "list[str]", cwd: Path, env: "dict | None" = None) -> subprocess.CompletedProcess:
    """Run python on args. An env value of None removes that variable."""
    full_env = dict(os.environ)
    for k, v in (env or {}).items():
        if v is None:
            full_env.pop(k, None)
        else:
            full_env[k] = v
    return subprocess.run([sys.executable, *args], cwd=str(cwd), capture_output=True, text=True, env=full_env)


def result_of(proc: subprocess.CompletedProcess) -> dict:
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("RESULT ")]
    assert lines, "no RESULT line in stdout:\n%s\n%s" % (proc.stdout, proc.stderr)
    return json.loads(lines[-1][len("RESULT "):])


@contextmanager
def patched_env(**changes):
    """Temporarily set (or with None remove) environment variables in this process."""
    old = {k: os.environ.get(k) for k in changes}
    for k, v in changes.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    try:
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def fake_yamlreel(path: Path, version: str = "0.3.1", story: bool = True, contact: bool = True, validate: bool = True,
                  slow: bool = False) -> Path:
    """A shell stand-in for yamlreel. slow=True makes real validate/render calls sleep (probe calls still pass)."""
    lines = ["#!/bin/sh", 'case "$1" in']
    lines.append('  --version) echo "%s";;' % version)
    lines.append("  story) exit %d;;" % (0 if story else 2))
    lines.append('  render) if [ "$2" = "--help" ]; then echo "usage: render %s"; exit 0; fi' % ("--contact-frames" if contact else ""))
    lines.append("    sleep 30;;" if slow else "    exit 1;;")
    lines.append('  validate) case "$2" in *yamlreel-probe-*) exit %d;; esac' % (0 if validate else 1))
    lines.append("    sleep 30;;" if slow else "    exit 0;;")
    lines.append("esac")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def path_without_yamlreel() -> str:
    """$PATH minus every folder that holds a yamlreel executable."""
    keep = [d for d in os.environ.get("PATH", "").split(os.pathsep) if d and not (Path(d) / "yamlreel").exists()]
    return os.pathsep.join(keep)


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
    assert VERSION_SPEC in text, "SKILL.md must quote the required yamlreel range %s" % VERSION_SPEC
    assert VERSION_SPEC in (ROOT / "README.md").read_text(encoding="utf-8"), "README.md must quote %s" % VERSION_SPEC
    assert "yamlreel-skill" not in "".join(p.read_text(encoding="utf-8") for p in
                                           (ROOT / "README.md", ROOT / "SKILL.md", ROOT / ".github" / "workflows" / "ci.yml"))
    assert "YAMLREEL_SPEC" in (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")


@case
def test_hygiene() -> None:
    bad = []
    for p in ROOT.rglob("*"):
        rel = p.relative_to(ROOT)
        if not p.is_file() or rel.parts[0] in (".git", "docs", "yamlreel-output", "out") or "__pycache__" in rel.parts:
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


GOOD_SPEC = "theme: midnight\nformats: [square]\nmeta:\n  title: Greeting\nscenes:\n  - type: title\n    title: Hello\n    seconds: 1\n"


def secret_cases() -> "list[tuple[str, str]]":
    """(label, text). Built from pieces so this file never holds a real-looking token."""
    return [
        ("aws", "AKIA" + "ABCDEFGHIJKLMNOP"),
        ("sk", "sk-" + "a1B2" * 6),
        ("sk-proj", "sk-proj-" + "a1_B2-" * 5),
        ("github ghp", "ghp_" + "a" * 24),
        ("github gho", "gho_" + "b" * 24),
        ("github ghs", "ghs_" + "c" * 24),
        ("github pat", "github_pat_" + "11ABC"),
        ("google", "AIza" + "x" * 35),
        ("stripe sk_live", "sk_live_" + "a1" * 8),
        ("stripe rk_live", "rk_live_" + "b2" * 8),
        ("gitlab", "glpat-" + "abc123"),
        ("slack xoxb", "xoxb-" + "123"),
        ("slack xoxa", "xoxa-" + "123"),
        ("slack xoxr", "xoxr-" + "123"),
        ("jwt", "eyJhbGciOiJIUzI1NiJ9" + "." + "eyJzdWIiOiIxMjM0NTY3ODkwIn0"),
        ("private key", "-----BEGIN " + "RSA PRIVATE KEY-----"),
        ("password assignment", "password: hunter2xyz"),
        ("token assignment", "token = abc123def456"),
        ("api key assignment", "api_key: \"" + "k3y" * 4 + "\""),
        ("secret assignment", "secret: s3cr3t-value"),
        ("django SECRET_KEY", "SECRET_KEY = 'django-insecure-x9k2m4p7q1'"),
        ("AWS_SECRET_ACCESS_KEY", "AWS_SECRET_ACCESS_KEY=" + "wJalrXUtnFEMI/K7MDENG/bPxRfiCY"),
        ("bearer", "Authorization: Bearer " + "abcdef0123456789abcdef"),
        ("DATABASE_URL with creds", "DATABASE_URL=postgres://admin:s3cr3tpw@db.internal:5432/app"),
        ("escaped quotes", 'password: \\"hunter2xyz\\"'),
        ("single quotes (doubled once embedded in YAML)", "password: 'hunter2xyz'"),
        ("OPENAI_API_KEY", "OPENAI_API_KEY=" + "abc123def456ghi789"),
        ("pwd", "pwd=hunter2"),
        ("auth", "auth: x9f8a7b6c5d4"),
        ("short password", "password: hunter2"),
        ("stripe test", "sk_test_" + "a1" * 6),
        ("huggingface", "hf_" + "aB3" * 11),
        ("npm", "npm_" + "aB3" * 12),
        ("slack app", "xapp-1-A0123"),
        ("sendgrid", "SG." + "a" * 22 + "." + "b" * 22),
    ]


@case
def test_preflight() -> None:
    with tempfile.TemporaryDirectory() as proj, tempfile.TemporaryDirectory() as elsewhere:
        proj_p, other = Path(proj).resolve(), Path(elsewhere).resolve()

        def spec(name: str, text: str, where: Path = proj_p) -> Path:
            p = where / name
            p.write_text(text, encoding="utf-8")
            return p

        r = run([str(RENDER), str(spec("out.yaml", GOOD_SPEC, other)), "--stage", "preview"], proj_p)
        assert r.returncode == 2, "outside cwd: %d" % r.returncode
        assert result_of(r)["ok"] is False
        r = run([str(RENDER), str(spec("todo.yaml", GOOD_SPEC.replace("Hello", "TODO fix"))), "--stage", "preview"], proj_p)
        assert r.returncode == 2, "TODO: %d" % r.returncode
        r = run([str(RENDER), str(spec("todo2.yaml", GOOD_SPEC + "# TODO later\n")), "--stage", "preview"], proj_p)
        assert r.returncode == 0, "TODO in comment should pass: %d %s" % (r.returncode, r.stderr)
        good = str(spec("good.yaml", GOOD_SPEC))
        r = run([str(RENDER), good, "--stage", "preview", "--voice-url", "https://api.example.com/mcp/"], proj_p)
        assert r.returncode == 2, "remote voice url: %d" % r.returncode
        r = run([str(RENDER), good, "--stage", "preview", "--out", str(other / "o")], proj_p)
        assert r.returncode == 2, "out dir outside cwd: %d" % r.returncode


@case
def test_secret_patterns() -> None:
    with tempfile.TemporaryDirectory() as proj:
        proj_p = Path(proj).resolve()
        for label, secret in secret_cases():
            p = proj_p / "secret.yaml"
            p.write_text(GOOD_SPEC.replace("title: Hello", "title: Hello\n    subtitle: '%s'" % secret.replace("'", "''")),
                         encoding="utf-8")
            r = run([str(RENDER), str(p), "--stage", "preview"], proj_p)
            assert r.returncode == 2, "%s: expected exit 2, got %d\n%s" % (label, r.returncode, r.stderr)
            assert "possible secret" in r.stderr, "%s: %s" % (label, r.stderr)
            assert result_of(r)["ok"] is False


@case
def test_secret_find_secret_direct() -> None:
    for label, secret in secret_cases():
        assert render_mod.find_secret(secret), "%s not flagged: %r" % (label, secret)
    doubled = "subtitle: 'password: " + "''hunter2xyz''" + "'"
    assert render_mod.find_secret(doubled), "doubled single quotes"
    for text in ("api_key: \"YOUR_KEY\"", "api_key = <your key>", "token: xxx", "password: ...", "password: ${DB_PASSWORD}",
                 "password: $DB_PASSWORD", "SECRET_KEY=MY_SECRET_NAME", "Authorization: Bearer YOUR_TOKEN_HERE_PLEASE",
                 "DATABASE_URL=postgres://user:${DB_PASS}@db/app", "DATABASE_URL=postgres://user:<password>@db/app",
                 "api_key: ****", "http://localhost:8080/path@x"):
        assert not render_mod.find_secret(text), "placeholder flagged: %r" % text


@case
def test_secret_prose_not_flagged() -> None:
    prose = ["The token: refresh it", "Never share your secret: keep it safe", "disk-based caching of the layer-cache-key-x",
             "a password manager", "tokens: reused", "api key rotation: monthly", "sk-short", "secret: rate-limiting",
             "Secret: hyphen-ated words are prose", "Bearer authentication", "the auth: layer", "token: refresh_flow"]
    with tempfile.TemporaryDirectory() as proj:
        proj_p = Path(proj).resolve()
        for i, text in enumerate(prose):
            spec = proj_p / ("prose%d.yaml" % i)
            spec.write_text(GOOD_SPEC.replace("Hello", text.replace('"', "'")), encoding="utf-8")
            try:
                render_mod.preflight(spec, proj_p / "out", None, proj_p)  # must pass: no exception at all
            except render_mod.Refused as e:
                raise AssertionError("prose %r refused: %s" % (text, e))


@case
def test_placeholder_spec_passes() -> None:
    with tempfile.TemporaryDirectory() as proj:
        proj_p = Path(proj).resolve()
        p = proj_p / "ph.yaml"
        p.write_text(GOOD_SPEC.replace("title: Hello", "title: Hello\n    subtitle: 'api_key = \"YOUR_KEY\"'"), encoding="utf-8")
        r = run([str(RENDER), str(p), "--stage", "preview"], proj_p)
        assert r.returncode == 0, "placeholder must pass: %d\n%s" % (r.returncode, r.stderr)


@case
def test_path_escapes() -> None:
    with tempfile.TemporaryDirectory() as proj, tempfile.TemporaryDirectory() as elsewhere:
        proj_p, other = Path(proj).resolve(), Path(elsewhere).resolve()
        (other / "x.yaml").write_text(GOOD_SPEC, encoding="utf-8")
        (proj_p / "link.yaml").symlink_to(other / "x.yaml")
        r = run([str(RENDER), "link.yaml", "--stage", "preview"], proj_p)
        assert r.returncode == 2, "symlinked spec escaping cwd: %d\n%s" % (r.returncode, r.stderr)
        (proj_p / "good.yaml").write_text(GOOD_SPEC, encoding="utf-8")
        (proj_p / "outlink").symlink_to(other, target_is_directory=True)
        r = run([str(RENDER), "good.yaml", "--stage", "preview", "--out", "outlink/o"], proj_p)
        assert r.returncode == 2, "symlinked out dir escaping cwd: %d\n%s" % (r.returncode, r.stderr)
        assert not (other / "o").exists()
        (proj_p / "sub").mkdir()
        r = run([str(RENDER), "sub/../../" + other.name + "/x.yaml", "--stage", "preview"], proj_p)
        assert r.returncode == 2, "'..' spec path: %d\n%s" % (r.returncode, r.stderr)
        r = run([str(RENDER), "good.yaml", "--stage", "preview", "--out", "sub/../../escape"], proj_p)
        assert r.returncode == 2, "'..' out path: %d\n%s" % (r.returncode, r.stderr)


@case
def test_refuses_home_and_root() -> None:
    for d in (Path.home(), Path("/")):
        r = run([str(RENDER), "nonexistent.yaml", "--stage", "preview"], d)
        assert r.returncode == 2 and "home or the filesystem root" in r.stderr, (d, r.returncode, r.stderr)
        assert result_of(r)["ok"] is False


@case
def test_usage_errors() -> None:
    with tempfile.TemporaryDirectory() as proj:
        proj_p = Path(proj).resolve()
        (proj_p / "good.yaml").write_text(GOOD_SPEC, encoding="utf-8")
        for bad in (["good.yaml", "--contact-frames", "0"], ["good.yaml", "--contact-frames", "9"],
                    ["good.yaml", "--contact-frames", "x"], ["good.yaml", "--stage", "bogus"], []):
            r = run([str(RENDER), *bad], proj_p)
            assert r.returncode == 4, "%s: expected 4, got %d\n%s" % (bad, r.returncode, r.stderr)
            res = result_of(r)
            assert res["ok"] is False and res["stage"] == "usage", res
        assert not (proj_p / "out").exists(), "usage errors must not create output"
        r = run([str(RENDER), "good.yaml", "--stage", "preview", "--contact-frames", "2"], proj_p)
        assert r.returncode == 0, r.stderr


@case
def test_default_out_is_next_to_spec() -> None:
    with tempfile.TemporaryDirectory() as proj:
        proj_p = Path(proj).resolve()
        for slug in ("a", "b"):
            (proj_p / slug).mkdir()
            (proj_p / slug / "spec.yaml").write_text(GOOD_SPEC, encoding="utf-8")
            r = run([str(RENDER), "%s/spec.yaml" % slug, "--stage", "preview"], proj_p)
            assert r.returncode == 0, r.stderr
            res = result_of(r)
            assert all(str(proj_p / slug / "out") in info["video"] for info in res["formats"].values()), res
        assert not (proj_p / "yamlreel-output").exists()
        assert (proj_p / "a" / "out" / "render-log.txt").is_file() and (proj_p / "b" / "out" / "render-log.txt").is_file()


@case
def test_subprocess_failures() -> None:
    with tempfile.TemporaryDirectory() as proj:
        proj_p = Path(proj).resolve()
        (proj_p / "good.yaml").write_text(GOOD_SPEC, encoding="utf-8")
        slow = fake_yamlreel(proj_p / "slow.sh", slow=True)
        r = run([str(RENDER), "good.yaml", "--stage", "preview"], proj_p,
                env={"YAMLREEL_BIN": str(slow), "YAMLREEL_RENDER_TIMEOUT": "2"})
        assert r.returncode == 1 and "timed out" in r.stderr, (r.returncode, r.stderr)
        assert result_of(r)["ok"] is False
        noexec = proj_p / "noexec"
        noexec.write_text("x", encoding="utf-8")
        noexec.chmod(0o644)
        # find_yamlreel skips a binary it cannot run, so the CLI reports "not found" ...
        r = run([str(RENDER), "good.yaml", "--stage", "preview"], proj_p,
                env={"YAMLREEL_BIN": str(noexec), "YAMLREEL_VENV": str(proj_p / "novenv"), "PATH": path_without_yamlreel()})
        assert r.returncode == 1 and "yamlreel not found" in r.stderr, (r.returncode, r.stderr)
        assert result_of(r)["ok"] is False
        # ... and run_yamlreel itself turns an OS error into a failed process.
        done = render_mod.run_yamlreel([str(noexec), "validate", "x"], render_mod.Logger(None))
        assert done.returncode == 1 and "cannot run yamlreel" in done.stderr, done
        (proj_p / "afile").write_text("x", encoding="utf-8")
        r = run([str(RENDER), "good.yaml", "--stage", "preview", "--out", "afile/sub"], proj_p)
        assert r.returncode == 1 and "cannot create output folder" in r.stderr, (r.returncode, r.stderr)
        assert result_of(r)["ok"] is False


@case
def test_timeout_env_fallback() -> None:
    for value, expected in (("1", 3600), ("0", 3600), ("-5", 3600), ("abc", 3600), ("", 3600), ("2", 2), ("90", 90)):
        with patched_env(YAMLREEL_RENDER_TIMEOUT=value):
            assert render_mod.timeout_for(3600) == expected, (value, render_mod.timeout_for(3600))
    with patched_env(YAMLREEL_RENDER_TIMEOUT=None):
        assert render_mod.timeout_for(120) == 120


NARRATED_SPEC = GOOD_SPEC.replace("    seconds: 1\n", "    seconds: 1\n    narration: Hello there.\n")


@case
def test_voice_url() -> None:
    with tempfile.TemporaryDirectory() as proj:
        proj_p = Path(proj).resolve()
        (proj_p / "narrated.yaml").write_text(NARRATED_SPEC, encoding="utf-8")
        for bad in ("http://127.0.0.1@evil.example.com/mcp/", "http://evil.example.com\\@127.0.0.1/mcp/",
                    "http://localhost.evil.example.com/mcp/", "http://127.0.0.1:99999/mcp/",
                    "http://127.0.0.1/ x", "ftp://127.0.0.1/mcp/", "http://u:hunter2pw@evil.example.com/mcp/",
                    "http://alice:hunter2pw@127.0.0.1:9/mcp/", "http://alice@127.0.0.1:9/mcp/",
                    "http://:hunter2pw@localhost:9/mcp/", "https://alice:hunter2pw@[::1]:9/mcp/"):
            r = run([str(RENDER), "narrated.yaml", "--stage", "preview", "--voice-url", bad], proj_p)
            assert r.returncode == 2, "%r: expected 2, got %d\n%s" % (bad, r.returncode, r.stderr)
            everything = r.stderr + r.stdout
            assert "hunter2pw" not in everything and "alice" not in everything, "credentials leaked: %s" % everything
            assert result_of(r)["ok"] is False
        assert not (proj_p / "out").exists(), "a refused voice url must not create output or a log"
        r = run([str(RENDER), "narrated.yaml", "--stage", "preview", "--voice-url", "http://127.0.0.1:9/mcp/"], proj_p)
        assert r.returncode in (0, 1), "local voice url without credentials must pass preflight (got %d)\n%s" % (
            r.returncode, r.stderr)
        assert render_mod.scrub("boom http://alice:hunter2pw@host/x") == "boom http://***@host/x"
        assert "hunter2pw" not in render_mod.result_line("x", False, ["http://alice:hunter2pw@host/x"], {}, None)


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
        assert not (Path(proj) / "out" / "final").exists(), "final must not run"
        r = run([str(RENDER), str(p), "--stage", "all", "--allow-warnings"], Path(proj))
        assert r.returncode == 0, "allow-warnings: %d\n%s" % (r.returncode, r.stderr)


@case
def test_check_setup() -> None:
    r = run([str(CHECK), "--json"], ROOT)
    data = json.loads(r.stdout)
    assert r.returncode == 0 and data["ok"], r.stdout
    names = {c["name"]: c for c in data["checks"]}
    assert names["features"]["ok"] and names["smoke-render"]["ok"], names
    # An empty YAMLREEL_FONT_DIR adds nothing; the system fonts are still searched, and the smoke render rules.
    with tempfile.TemporaryDirectory() as empty:
        r = run([str(CHECK), "--json"], ROOT, env={"YAMLREEL_FONT_DIR": empty})
        data = json.loads(r.stdout)
        assert r.returncode == 0 and data["ok"], r.stdout


@case
def test_check_setup_units() -> None:
    assert VERSION_SPEC == ">=0.3.0,<0.4", VERSION_SPEC
    assert check_setup.PIN == "yamlreel[ffmpeg]" + VERSION_SPEC
    with tempfile.TemporaryDirectory() as d:
        old = os.environ.get("YAMLREEL_FONT_DIR")
        os.environ["YAMLREEL_FONT_DIR"] = d
        try:
            dirs = check_setup.font_dirs()
            assert dirs[0] == Path(d) and len(dirs) > 1, dirs
            for f in check_setup.FONTS:
                (Path(d) / f).write_text("x", encoding="utf-8")
            found, missing = check_setup.find_fonts()
            assert not missing and len(found) == len(check_setup.FONTS), (found, missing)
        finally:
            if old is None:
                os.environ.pop("YAMLREEL_FONT_DIR", None)
            else:
                os.environ["YAMLREEL_FONT_DIR"] = old
    checks = [check_setup.check("fonts", False, "missing x", "fix it"), check_setup.check("ffmpeg", False, "none", "fix"),
              check_setup.check("python", False, "none", "fix"), check_setup.check("smoke-render", True, "ok")]
    check_setup.downgrade_when_smoke_passes(checks)
    assert [c["ok"] for c in checks] == [True, True, False, True], checks
    assert checks[0]["warning"] and checks[0]["fix"] == "fix it"
    failed = [check_setup.check("fonts", False, "missing x", "fix it"), check_setup.check("smoke-render", False, "bad")]
    check_setup.downgrade_when_smoke_passes(failed)
    assert not failed[0]["ok"], "fonts stay a failure when the smoke render fails"


@case
def test_install_json_stdout_is_pure_json() -> None:
    with tempfile.TemporaryDirectory() as d:
        env = {"YAMLREEL_VENV": str(Path(d) / "venv"), "YAMLREEL_SPEC": str(Path(d) / "no-such-package-dir")}
        r = run([str(CHECK), "--install", "--json"], ROOT, env=env)
        data = json.loads(r.stdout)  # raises if progress text leaked into stdout
        assert r.returncode == 1 and data["ok"] is False, r.stdout
        assert "install failed" in r.stderr, r.stderr


@case
def test_feature_probe_and_version() -> None:
    with tempfile.TemporaryDirectory() as d:
        dp = Path(d).resolve()
        old = fake_yamlreel(dp / "yamlreel", version="yamlreel 0.2.2", story=False, contact=False)
        ok, detail = check_setup.probe_features(str(old))
        assert not ok and "story" in detail and "--contact-frames" in detail, detail
        empty_venv = str(dp / "novenv")
        r = run([str(CHECK), "--json"], ROOT, env={"YAMLREEL_BIN": str(old), "YAMLREEL_VENV": empty_venv,
                                                    "PATH": path_without_yamlreel()})
        data = json.loads(r.stdout)
        assert r.returncode == 1 and not data["ok"], r.stdout
        feat = [c for c in data["checks"] if c["name"] == "features"][0]
        assert not feat["ok"] and "upgrade yamlreel" in feat["fix"], feat
        link = dp / "link-to-yamlreel"
        link.symlink_to(Path(YAMLREEL).resolve() if YAMLREEL else old)
        assert check_setup.probe_features(str(link))[0] or not YAMLREEL
        # validate is part of the probe: help text alone is not enough
        nov = fake_yamlreel(dp / "novalidate", validate=False)
        ok, detail = check_setup.probe_features(str(nov))
        assert not ok and "validate" in detail, detail


@case
def test_assess_unreleased_build_branch() -> None:
    with tempfile.TemporaryDirectory() as d:
        dp = Path(d).resolve()
        a = check_setup.assess(str(fake_yamlreel(dp / "a", version="yamlreel 0.2.2")))
        assert a.usable and a.unreleased and a.feat_ok, a  # older number, has the features: passes
        a = check_setup.assess(str(fake_yamlreel(dp / "b", version="yamlreel 0.3.5")))
        assert a.usable and not a.unreleased, a
        a = check_setup.assess(str(fake_yamlreel(dp / "c", version="yamlreel 0.4.0")))
        assert not a.usable and a.feat_ok, a  # features but out of range
        a = check_setup.assess(str(fake_yamlreel(dp / "d", version="yamlreel 0.3.0", story=False)))
        assert not a.usable and not a.feat_ok and not a.unreleased, a
        a = check_setup.assess(str(fake_yamlreel(dp / "e", version="yamlreel 0.2.2", story=False)))
        assert not a.usable and not a.unreleased, a  # old number and no features
        a = check_setup.assess(str(fake_yamlreel(dp / "f", version="no version here")))
        assert not a.usable and not a.runs, a
        a = check_setup.assess(str(dp / "does-not-exist"))
        assert not a.usable and a.error, a


@case
def test_find_yamlreel_skips_unusable_and_orders() -> None:
    with tempfile.TemporaryDirectory() as d:
        dp = Path(d).resolve()
        bad_dir, good_dir, other_dir = dp / "badbin", dp / "venv" / "bin", dp / "otherbin"
        for x in (bad_dir, good_dir, other_dir):
            x.mkdir(parents=True)
        bad = fake_yamlreel(bad_dir / "yamlreel", version="yamlreel 0.2.2", story=False, contact=False)
        good = fake_yamlreel(good_dir / "yamlreel")
        other = fake_yamlreel(other_dir / "yamlreel", version="yamlreel 0.3.2")
        path = os.pathsep.join([str(bad_dir), path_without_yamlreel()])
        # old yamlreel on PATH, good one in the skill venv: the venv wins and check_setup approves exactly that binary
        with patched_env(YAMLREEL_BIN=None, YAMLREEL_VENV=str(dp / "venv"), PATH=path):
            assert check_setup.find_yamlreel() == str(good), check_setup.find_yamlreel()
            assert check_setup.resolution_check(str(good)) is None
            mismatch = check_setup.resolution_check(str(bad))
            assert mismatch and not mismatch["ok"] and "would run" in mismatch["detail"], mismatch
        # an unusable $YAMLREEL_BIN falls through to the venv
        with patched_env(YAMLREEL_BIN=str(bad), YAMLREEL_VENV=str(dp / "venv"), PATH=path):
            assert check_setup.find_yamlreel() == str(good)
        # a usable $YAMLREEL_BIN wins over the venv; the venv binary then fails the resolution check
        with patched_env(YAMLREEL_BIN=str(other), YAMLREEL_VENV=str(dp / "venv"), PATH=path):
            assert check_setup.find_yamlreel() == str(other)
            mismatch = check_setup.resolution_check(str(good))
            assert mismatch and not mismatch["ok"] and str(other) in mismatch["detail"], mismatch
        # PATH is the last resort
        with patched_env(YAMLREEL_BIN=None, YAMLREEL_VENV=str(dp / "novenv"), PATH=os.pathsep.join([str(other_dir), path_without_yamlreel()])):
            assert check_setup.find_yamlreel() == str(other)
        with patched_env(YAMLREEL_BIN=None, YAMLREEL_VENV=str(dp / "novenv"), PATH=path):
            assert check_setup.find_yamlreel() is None
        # the CLI: with only an old yamlreel around, render.py says so
        (dp / "good.yaml").write_text(GOOD_SPEC, encoding="utf-8")
        r = run([str(RENDER), "good.yaml", "--stage", "preview"], dp,
                env={"YAMLREEL_BIN": None, "YAMLREEL_VENV": str(dp / "novenv"), "PATH": path})
        assert r.returncode == 1 and "yamlreel not found" in r.stderr, (r.returncode, r.stderr)


@case
def test_install_guards() -> None:
    with tempfile.TemporaryDirectory() as d:
        dp = Path(d).resolve()
        # a non-default venv whose python is too old is never deleted
        venv = dp / "custom-venv"
        (venv / "bin").mkdir(parents=True)
        (venv / "pyvenv.cfg").write_text("home = /nowhere\n", encoding="utf-8")
        py = venv / "bin" / "python"
        py.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        py.chmod(0o755)
        r = run([str(CHECK), "--install", "--json"], ROOT, env={"YAMLREEL_VENV": str(venv)})
        assert r.returncode == 1 and "not the default skill venv" in r.stderr, (r.returncode, r.stderr)
        assert (venv / "pyvenv.cfg").is_file() and py.is_file(), "custom venv must not be removed"
        json.loads(r.stdout)
        # the override of the pin is announced
        env = {"YAMLREEL_VENV": str(dp / "v2"), "YAMLREEL_SPEC": str(dp / "no-such-package-dir")}
        r = run([str(CHECK), "--install", "--json"], ROOT, env=env)
        assert "YAMLREEL_SPEC is set" in r.stderr and "instead of the pinned" in r.stderr, r.stderr


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
    test_secret_patterns()
    test_secret_find_secret_direct()
    test_secret_prose_not_flagged()
    test_placeholder_spec_passes()
    test_path_escapes()
    test_refuses_home_and_root()
    test_usage_errors()
    test_default_out_is_next_to_spec()
    test_subprocess_failures()
    test_timeout_env_fallback()
    test_voice_url()
    test_warning_blocks_final()
    test_check_setup()
    test_check_setup_units()
    test_feature_probe_and_version()
    test_assess_unreleased_build_branch()
    test_find_yamlreel_skips_unusable_and_orders()
    test_install_guards()
    test_install_json_stdout_is_pure_json()
    for ex in sorted((ROOT / "examples").glob("*.yaml")):
        name = "example_%s" % ex.stem

        def run_example(ex: Path = ex) -> None:
            example_test(ex, args.preview)
        run_example.__name__ = name  # set before @case wraps it so PASS/FAIL lines carry the example name
        print("-- %s" % name)
        case(run_example)()
    print("\n%d failure(s)" % len(FAILURES) if FAILURES else "\nall passed")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
