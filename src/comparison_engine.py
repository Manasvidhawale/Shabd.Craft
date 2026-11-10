"""
Shabd.Craft — Comparison Engine

Side-by-side comparison of prompt versions on shared test cases.
"""

from __future__ import annotations

import difflib
import html
import json
import re
from src.schemas import (
    VersionComparison, EvaluationResult, PromptVersion,
    ExecutionStatus,
)


def compare_versions(
    version_a: dict,
    version_b: dict,
    results_a: list[dict],
    results_b: list[dict],
) -> VersionComparison:
    """
    Compare two prompt versions using their evaluation results.

    Both should have been evaluated on the same test cases.
    """
    # Calculate aggregate scores
    scores_a = _aggregate_criterion_scores(results_a)
    scores_b = _aggregate_criterion_scores(results_b)
    overall_a = _average_overall(results_a)
    overall_b = _average_overall(results_b)

    # Determine winner
    limitations = []
    count_a = len([r for r in results_a if r.get("execution_status") == "success"])
    count_b = len([r for r in results_b if r.get("execution_status") == "success"])
    test_count = max(count_a, count_b)

    if test_count < 5:
        limitations.append(f"Small sample size ({test_count} test cases).")
    if count_a != count_b:
        limitations.append(f"Different success counts: {count_a} vs {count_b}.")

    demo_a = any(r.get("is_demo") for r in results_a)
    demo_b = any(r.get("is_demo") for r in results_b)
    if demo_a or demo_b:
        limitations.append("Results include simulated demo evaluations.")

    diff = overall_a - overall_b
    if abs(diff) < 2:
        winner = None
        recommendation = (
            f"Scores are very close ({overall_a:.1f} vs {overall_b:.1f}). "
            f"The difference is within evaluation noise. Neither version is clearly better."
        )
    elif diff > 0:
        winner = version_a.get("id", "A")
        recommendation = (
            f"Version '{version_a.get('version_label', 'A')}' scored {overall_a:.1f} vs "
            f"{overall_b:.1f} (+{diff:.1f} points). It performed better across the evaluated test cases."
        )
    else:
        winner = version_b.get("id", "B")
        recommendation = (
            f"Version '{version_b.get('version_label', 'B')}' scored {overall_b:.1f} vs "
            f"{overall_a:.1f} (+{-diff:.1f} points). It performed better across the evaluated test cases."
        )

    return VersionComparison(
        version_a_id=version_a.get("id", ""),
        version_b_id=version_b.get("id", ""),
        version_a_label=version_a.get("version_label", "Version A"),
        version_b_label=version_b.get("version_label", "Version B"),
        version_a_scores=scores_a,
        version_b_scores=scores_b,
        version_a_overall=overall_a,
        version_b_overall=overall_b,
        winner=winner,
        recommendation=recommendation,
        limitations=limitations,
        test_case_count=test_count,
    )


def _aggregate_criterion_scores(results: list[dict]) -> dict[str, float]:
    """Aggregate criterion scores from evaluation results."""
    totals: dict[str, list[float]] = {}
    for r in results:
        if r.get("execution_status") != "success":
            continue
        scores_raw = r.get("criterion_scores", "[]")
        if isinstance(scores_raw, str):
            scores = json.loads(scores_raw)
        else:
            scores = scores_raw
        for s in scores:
            name = s.get("name", "") if isinstance(s, dict) else getattr(s, "name", "")
            score = s.get("score", 0) if isinstance(s, dict) else getattr(s, "score", 0)
            if name:
                totals.setdefault(name, []).append(float(score))

    return {k: round(sum(v) / len(v), 1) for k, v in totals.items()}


def _average_overall(results: list[dict]) -> float:
    """Average overall score from results."""
    scores = [
        r.get("overall_score", 0)
        for r in results
        if r.get("execution_status") == "success"
    ]
    return round(sum(scores) / len(scores), 1) if scores else 0.0


def get_side_by_side_outputs(
    results_a: list[dict],
    results_b: list[dict],
) -> list[dict]:
    """Match outputs from two versions by test_case_id for comparison."""
    map_a = {r["test_case_id"]: r for r in results_a}
    map_b = {r["test_case_id"]: r for r in results_b}

    all_tc_ids = list(dict.fromkeys(list(map_a.keys()) + list(map_b.keys())))
    rows = []
    for tc_id in all_tc_ids:
        ra = map_a.get(tc_id, {})
        rb = map_b.get(tc_id, {})
        rows.append({
            "test_case_id": tc_id,
            "output_a": ra.get("generated_output", "—"),
            "output_b": rb.get("generated_output", "—"),
            "score_a": ra.get("overall_score", 0),
            "score_b": rb.get("overall_score", 0),
            "status_a": ra.get("execution_status", "—"),
            "status_b": rb.get("execution_status", "—"),
        })
    return rows


def build_word_diff_html(text_a: str, text_b: str) -> str:
    """
    Build an HTML word-level diff comparing text_a -> text_b.

    Escapes HTML entities safely and preserves line breaks.
    """
    tokens_a = re.findall(r"\S+|\n|[ \t]+", text_a or "")
    tokens_b = re.findall(r"\S+|\n|[ \t]+", text_b or "")
    matcher = difflib.SequenceMatcher(None, tokens_a, tokens_b)

    parts = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            parts.append(_format_diff_tokens(tokens_a[i1:i2], kind="equal"))
        elif tag in ("delete", "replace"):
            parts.append(_format_diff_tokens(tokens_a[i1:i2], kind="delete"))
            if tag == "replace":
                parts.append(_format_diff_tokens(tokens_b[j1:j2], kind="insert"))
        elif tag == "insert":
            parts.append(_format_diff_tokens(tokens_b[j1:j2], kind="insert"))

    body = "".join(parts)
    return (
        "<div style='background:#1e2130;border:1px solid #2a2d3e;border-radius:8px;"
        "padding:14px;font-family:JetBrains Mono,monospace;font-size:0.84rem;"
        "line-height:1.6;color:#e8eaed;white-space:pre-wrap;'>"
        f"{body}</div>"
    )


def _format_diff_tokens(tokens: list[str], kind: str) -> str:
    out = []
    for tok in tokens:
        if tok == "\n":
            out.append("<br>")
            continue
        escaped = html.escape(tok)
        if kind == "delete":
            if tok.strip():
                out.append(
                    "<span style='background:rgba(248,113,113,0.18);color:#f87171;"
                    "text-decoration:line-through;border-radius:3px;padding:0 2px;'>"
                    f"{escaped}</span>"
                )
            else:
                out.append(escaped)
        elif kind == "insert":
            if tok.strip():
                out.append(
                    "<span style='background:rgba(52,211,153,0.18);color:#34d399;"
                    "border-radius:3px;padding:0 2px;'>"
                    f"{escaped}</span>"
                )
            else:
                out.append(escaped)
        else:
            out.append(escaped)
    return "".join(out)
