#!/usr/bin/env python3
"""Reliability and efficiency metrics.

Two families, deliberately never blended:

  pass^k        does the agent succeed *consistently*
  pass_cost^k   what did that consistency cost in compute

`pass^k` is not `pass@k`, and the difference decides what the number means.
`pass@k` asks whether at least one of k attempts succeeds, which suits a setting
where a human picks the good one. `pass^k` asks whether **all** k succeed, which
is the question that matters when nobody is checking. A model you leave running
unsupervised has to be right every time, not once in eight tries.

The estimator over n observed trials with c successes is the probability that k
trials drawn without replacement from those n are all successes:

    pass^k = C(c, k) / C(n, k)

This is why small n is not merely imprecise but structurally unable to see the
failure mode. At n=2 the largest reportable k is 2. The literature finding that
motivates this module is that pass^1 above 70% routinely collapses below 25% at
k=8, so a suite that never runs 8 trials cannot observe its own instability.

Stdlib only.
"""
from __future__ import annotations

import math
from typing import Any

# Reported by default. k=1 is the familiar per-trial rate; k=8 is the point at
# which the literature reports single-trial scores collapsing.
DEFAULT_K_VALUES = (1, 2, 4, 8)

# Below this, a pass^k curve is too short to say anything about consistency.
MIN_N_FOR_CONSISTENCY_CLAIM = 8


def pass_hat_k(n: int, c: int, k: int) -> float | None:
    """Probability that k trials drawn from n observed trials all succeeded.

    Returns None when k exceeds n: that value was not measured, and reporting a
    zero would read as "it always fails" instead of "we never looked".
    """
    if k <= 0 or n <= 0 or k > n:
        return None
    if c < k:
        return 0.0
    return math.comb(c, k) / math.comb(n, k)


def pass_k_curve(n: int, c: int, ks: tuple[int, ...] = DEFAULT_K_VALUES) -> dict[str, float | None]:
    return {"pass^%d" % k: pass_hat_k(n, c, k) for k in ks}


def max_reportable_k(n: int) -> int:
    return max(0, n)


def consistency_claim_supported(n: int) -> bool:
    """Whether n is large enough for a consistency claim at the standard k."""
    return n >= MIN_N_FOR_CONSISTENCY_CLAIM


def pass_cost_k(pass_k: float | None, total_tokens: int, baseline_tokens: int) -> float | None:
    """Compute-normalized pass score.

        pass_cost^k = pass^k / (1 + log10(total / baseline))

    The baseline must be named wherever this is reported. It is a ratio against
    some other cell, so the number is meaningless without saying which one.
    """
    if pass_k is None:
        return None
    if total_tokens <= 0 or baseline_tokens <= 0:
        return None
    ratio = total_tokens / baseline_tokens
    return pass_k / (1.0 + math.log10(ratio)) if ratio > 0 else None


def step_ratio(optimal_steps: int | None, executed_steps: int | None) -> float | None:
    """Path efficiency: optimal / executed. 1.0 is perfect, near 0 is a loop.

    None when the task has not authored an optimal step count, since guessing
    one would invent the denominator of a published metric.
    """
    if not optimal_steps or not executed_steps or executed_steps <= 0:
        return None
    return optimal_steps / executed_steps


def summarize_usage(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Total token usage across rows, and whether every row reported it.

    Partial coverage is recorded rather than silently summed: a total over three
    of ten runs is not a total, and an efficiency metric built on one would be
    wrong in the flattering direction.

    A usage dict that exists but reports nothing does not count as coverage. Any
    real turn has prompt tokens, so all-zero means the backend never gave us
    counters, not that the run was free. Counting those rows produced a summary
    reading `complete: true` beside `total_tokens: 0`, which is incoherent and
    would let a broken cell pass for a measured one.
    """
    inp = out = counted = 0
    for row in rows:
        usage = row.get("usage") or {}
        row_in = int(usage.get("input_tokens") or 0)
        row_out = int(usage.get("output_tokens") or 0)
        if not usage or (row_in == 0 and row_out == 0):
            continue
        counted += 1
        inp += row_in
        out += row_out
    return {
        "input_tokens": inp,
        "output_tokens": out,
        "total_tokens": inp + out,
        "rows_with_usage": counted,
        "rows": len(rows),
        "complete": counted == len(rows) and counted > 0,
    }
