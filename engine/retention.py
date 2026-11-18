"""The one place the retention windows live.

`DATA.md` is the standard; this is the code that enforces it. Keep the two in step —
the published privacy statement names these numbers, so a change here is a change
there, and nowhere else. No literal window belongs anywhere else in the tree.

Why these exist at all: the expiry is not hygiene, it is the **licence to publish**.
The reading-level ledger can be public because it is time-limited; a permanent
archive of individuals' readings is a permanent resource for anyone who wants to use
it against them. The counts are what persist — see `DATA.md`, "Two tiers".
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

# Anti-abuse working value: how long a hashed network address is kept. It exists only
# to catch a burst of readings from one network — days, not months. (What enforces one
# reading per device is the device key, not this.)
ADDRESS_DAYS = 30

# How long a published release of the reading-level ledger lives before it is retired.
# The aggregates it produced are permanent; the rows are not.
RELEASE_DAYS = 90


def now_iso() -> str:
    """Now, as the ISO-8601 UTC stamp this project uses everywhere."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def retire_after(days: int) -> str:
    """The `retire_after` stamp for something retained for `days` from now."""
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
