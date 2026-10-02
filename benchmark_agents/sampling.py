"""Seeded case × elapsed-time sampling of captured answers."""

import random
from collections import Counter
from typing import Any

from .models import Plan


def select_rows(
    eligible: list[dict[str, Any]], rows: list[dict[str, Any]], plan: Plan
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Round-robin shuffled strata, not earliest completions; preserve exact selected IDs."""
    end = max((r.get("start_offset_ms", 0) for r in rows), default=0)
    buckets: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for row in sorted(eligible, key=lambda r: r["request_id"]):
        time_bin = (
            min(plan.time_bins - 1, int(row.get("start_offset_ms", 0) / end * plan.time_bins))
            if end
            else 0
        )
        buckets.setdefault((row["case_id"], time_bin), []).append(row)
    rng = random.Random(plan.sampling_seed)
    for bucket in buckets.values():
        rng.shuffle(bucket)
    keys = sorted(buckets)
    rng.shuffle(keys)
    selected = []
    counts: Counter = Counter()
    while len(selected) < min(len(eligible), plan.max_scored_requests):
        for key in keys:
            if buckets[key]:
                selected.append(buckets[key].pop())
                counts[key] += 1
            if len(selected) == min(len(eligible), plan.max_scored_requests):
                break
    return selected, {
        "policy": plan.sampling_policy,
        "seed": plan.sampling_seed,
        "time_bins": plan.time_bins,
        "observed_dispatch_window_ms": end,
        "eligible": len(eligible),
        "selected": len(selected),
        "fraction_of_eligible": len(selected) / len(eligible) if eligible else 0,
        "eligible_strata": len(keys),
        "selected_strata": len(counts),
        "strata": [{"case_id": k[0], "time_bin": k[1], "selected": counts[k]} for k in keys],
    }
