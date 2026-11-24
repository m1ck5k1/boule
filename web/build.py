"""Build the read path as static files.

    python3 web/build.py --out dist [--base-path /boule]

The split architecture: reading is static (GitHub Pages, an R2 bucket, any web
server, a USB stick), and only VOTING needs a live origin. That is what makes the
public site cheap and portable — egress was the only cost that scaled, and static
hosting removes it.

The pages are generated from the same SQLite the server reads, through the same
render module, so the static site and the live site cannot drift apart.
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import render  # noqa: E402

def build(db: str, out: Path, base_path: str = "", today: str | None = None) -> list[Path]:
    today = today or date.today().isoformat()
    out.mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    written: list[Path] = []
    try:
        # Every route the nav can reach, rendered through the same function the
        # server uses. Emitting only index.html left three nav links pointing at
        # files that did not exist.
        for path, filename, _label in render.routes_for(con):
            target = out / filename
            target.parent.mkdir(parents=True, exist_ok=True)   # per-bill pages nest
            target.write_text(render.render_route(path, con, today, base_path),
                              encoding="utf-8")
            written.append(target)
    finally:
        con.close()

    # static assets
    static_out = out / "static"
    static_out.mkdir(parents=True, exist_ok=True)
    for asset in sorted((HERE / "static").iterdir()):
        if asset.is_file():
            shutil.copy2(asset, static_out / asset.name)
            written.append(static_out / asset.name)

    # The manifest belongs at the SITE ROOT, not under /static/: its start_url and scope
    # are resolved relative to the manifest's OWN URL, so from the root "." means the
    # site root -- and the same holds in a subpath deploy, where the root is /boule/.
    manifest_out = out / "manifest.webmanifest"
    shutil.copy2(HERE / "manifest.webmanifest", manifest_out)
    written.append(manifest_out)

    # GitHub Pages serves 404.html for unknown paths; give it the site's own page
    # rather than GitHub's, so a bad link still looks like Boule.
    not_found = out / "404.html"
    not_found.write_text(
        render.page(
            "Boule — not found",
            render.masthead(["<b>404</b> — no such page"])
            + '<main id="main"><p class="empty">No such page.</p></main>',
            "", base_path=base_path),
        encoding="utf-8")
    written.append(not_found)

    return written


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=str(ROOT / "engine" / "boule.db"))
    ap.add_argument("--out", default=str(ROOT / "dist"))
    ap.add_argument("--base-path", default="",
                    help="URL prefix when not hosted at a domain root, "
                         "e.g. /boule for m1ck5k1.github.io/boule/")
    ap.add_argument("--today", default=None, help="override the date (determinism)")
    args = ap.parse_args()

    out = Path(args.out).resolve()
    written = build(args.db, out, args.base_path, args.today)

    total = sum(p.stat().st_size for p in written)
    print(f"built {len(written)} file(s) -> {out}")
    for p in written:
        print(f"  {p.relative_to(out)!s:22s} {p.stat().st_size:>8,} bytes")
    print(f"\ntotal {total:,} bytes  (base_path={args.base_path!r})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
