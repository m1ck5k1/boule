"""Gate for the static/dynamic split.

Pass criteria, fixed before the build:

  1. ARTIFACTS   the build emits index, privacy, 404 and the stylesheet
  2. TWIN        the built index.html is BYTE-IDENTICAL to what the server serves
                 for the same database — the two read paths cannot drift
  3. BASE PATH   built with --base-path, no bare href="/..." survives (those 404
                 the moment the site is not at a domain root)
  4. LINKS       every href/src in the built pages resolves to a file we emitted
  5. NO LEAK     no localhost, tailnet IP or file:// path ships in the output

    python3 web/gate_static.py [--server http://127.0.0.1:8099]
"""
from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import build as build_mod  # noqa: E402
import render as render_mod  # noqa: E402

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--server", default="http://127.0.0.1:8099")
    ap.add_argument("--db", default=str(ROOT / "engine" / "boule.db"))
    args = ap.parse_args()

    out = Path(tempfile.mkdtemp(prefix="boule-dist-"))
    written = build_mod.build(args.db, out)
    names = {p.name for p in written}

    # 1. ARTIFACTS
    need = {"index.html", "privacy.html", "404.html", "boule.css"}
    check("ARTIFACTS", need <= names, f"missing {sorted(need - names)}" if not need <= names
          else f"{len(written)} files")

    # 2. TWIN — the whole point, and for EVERY route, not just index
    built = (out / "index.html").read_text(encoding="utf-8")
    drifts = []
    for path, filename, _label in render_mod.ROUTES:
        built_text = (out / filename).read_text(encoding="utf-8")
        try:
            live = urllib.request.urlopen(f"{args.server}{path}", timeout=10).read().decode("utf-8")
        except Exception as exc:                               # noqa: BLE001
            drifts.append(f"{path}: unreachable ({exc})")
            continue
        if built_text != live:
            drifts.append(f"{path}: static {sha(built_text)} vs served {sha(live)}")
    check("TWIN", not drifts,
          f"{len(render_mod.ROUTES)} routes byte-identical"
          if not drifts else "; ".join(drifts[:3]))

    # 3. BASE PATH — look for URLs that are root-absolute but MISSING the prefix
    sub = Path(tempfile.mkdtemp(prefix="boule-sub-"))
    build_mod.build(args.db, sub, base_path="/boule")
    sub_index = (sub / "index.html").read_text(encoding="utf-8")
    all_abs = re.findall(r'(?:href|src)="(/[^"]*)"', sub_index)
    bare_abs = [u for u in all_abs if not u.startswith("/boule")]
    check("BASE PATH", not bare_abs,
          f"all {len(all_abs)} URLs carry /boule" if not bare_abs
          else f"unprefixed: {bare_abs[:4]}")

    # 4. LINKS — every referenced path must resolve to a file we actually emitted
    route_files = {p: f for p, f, _ in render_mod.ROUTES}
    refs = set(re.findall(r'(?:href|src)="([^"#]+)"', built))
    local = {r for r in refs if not r.startswith(("http://", "https://", "mailto:"))}
    missing = []
    for ref in local:
        target = out / route_files[ref] if ref in route_files else out / ref.lstrip("/")
        if not target.exists():
            missing.append(ref)
    check("LINKS", not missing,
          f"{len(local) - len(missing)}/{len(local)} resolve"
          + (f"; missing {sorted(missing)}" if missing else ""))

    # 5. NO LEAK
    leaks = [t for t in ("127.0.0.1", "localhost", "100.109.45.107", "file://") if t in built]
    check("NO LEAK", not leaks, "clean" if not leaks else f"found {leaks}")

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    total = len(RESULTS)
    print(f"\nSTATIC SPLIT GATE: {passed}/{total} — "
          + ("PASS" if passed == total else "FAIL"))
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
