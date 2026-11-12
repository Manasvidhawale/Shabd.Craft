"""
Shabd.Craft — Execution & Regression Harness

Provides:
1. Runtime reliability harness (input sanitization, output contract validation,
   and bounded auto-repair retries).
2. Regression quality gate (pass/fail threshold assertions for evaluation and security).
3. CLI runner (`python -m src.harness`) for automated CI/CD checks.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Optional

from src.config import settings
from src.database import Database
from src.evaluation_engine import aggregate_results, evaluate_batch
from src.guardrails import check_input_guardrails, check_output_guardrails
from src.prompt_engine import construct_prompt, get_provider
from src.schemas import (
    EvaluationMethod,
    EvaluationResult,
    EvaluationWeights,
    FewShotExample,
    LLMRequest,
    LLMResponse,
    OutputFormat,
    PromptVersion,
    PromptingTechnique,
    TestCase,
)
from src.security_evaluator import run_security_audit

_INJECTION_MARKERS = (
    "ignore all previous instructions",
    "ignore previous instructions",
    "system override:",
    "</user_input>",
    "</context>",
)


def sanitize_untrusted_input(input_data: str) -> tuple[str, bool]:
    """
    Neutralize closing boundary tags and flag obvious injection attempts
    before interpolating untrusted user input into a prompt template.
    """
    if not input_data:
        return input_data, False

    lower = input_data.lower()
    flagged = any(marker in lower for marker in _INJECTION_MARKERS)

    cleaned = re.sub(r"</\s*(user_input|context|system)\s*>", "[tag_removed]", input_data, flags=re.IGNORECASE)
    if cleaned != input_data:
        flagged = True

    return cleaned, flagged


def validate_output_contract(
    content: str,
    output_format: OutputFormat,
    required_keywords: list[str] | None = None,
    max_words: int | None = None,
) -> list[str]:
    """
    Validate LLM output against deterministic format and constraint rules.

    Returns a list of violation descriptions; an empty list means valid.
    """
    violations: list[str] = []
    text = (content or "").strip()

    if not text:
        return ["Response is empty."]

    if output_format == OutputFormat.JSON:
        try:
            json.loads(text)
        except json.JSONDecodeError as exc:
            violations.append(f"Invalid JSON output ({exc.msg}).")
    elif output_format == OutputFormat.BULLET_POINTS:
        bullets = re.findall(r"^[\-\*•]\s+", text, re.MULTILINE)
        if not bullets:
            violations.append("Expected bullet-point lines starting with '-', '*', or '•'.")
    elif output_format == OutputFormat.CSV:
        lines = [ln for ln in text.splitlines() if ln.strip()]
        if len(lines) < 2 or "," not in lines[0]:
            violations.append("Expected CSV output with a comma-separated header and at least one data row.")

    if required_keywords:
        lower = text.lower()
        missing = [kw for kw in required_keywords if kw.lower() not in lower]
        if missing:
            violations.append(f"Missing required keywords: {', '.join(missing)}.")

    if max_words is not None and max_words > 0:
        wc = len(text.split())
        if wc > max_words:
            violations.append(f"Word count {wc} exceeds limit of {max_words} words.")

    return violations


def execute_with_harness(
    version: PromptVersion,
    input_data: str = "",
    variables: dict[str, str] | None = None,
    required_keywords: list[str] | None = None,
    max_words: int | None = None,
    max_retries: int | None = None,
    sanitize_input: bool = True,
    enable_guardrails: bool = False,
    block_injection: bool = True,
    redact_pii: bool = True,
    banned_terms: list[str] | None = None,
) -> dict:
    """
    Execute a prompt inside a reliability harness with optional input/output guardrails,
    contract validation, and bounded self-repair retries.
    """
    retries = settings.max_retries if max_retries is None else max(0, int(max_retries))
    sanitized_input = input_data
    was_sanitized = False
    guardrail_report: dict | None = None

    if enable_guardrails:
        in_guard = check_input_guardrails(
            input_data,
            block_injection=block_injection,
            redact_pii=redact_pii,
            banned_terms=banned_terms,
        )
        if not in_guard["allowed"]:
            blocked_msg = f"[Blocked by Input Guardrail] {in_guard['blocked_reason']}"
            return {
                "response": LLMResponse(
                    content=blocked_msg,
                    model=version.model_name or settings.active_model,
                ),
                "attempts": 0,
                "repaired": False,
                "passed_contract": False,
                "validation_errors": [in_guard["blocked_reason"]],
                "input_sanitized": False,
                "guardrail_report": {"input": in_guard, "output": None},
            }
        sanitized_input = in_guard["processed_input"]
        was_sanitized = bool(in_guard["redactions"] or in_guard["warnings"])
        guardrail_report = {"input": in_guard, "output": None}
    elif sanitize_input and input_data:
        sanitized_input, was_sanitized = sanitize_untrusted_input(input_data)

    provider = get_provider()
    system_prompt, user_prompt = construct_prompt(version, sanitized_input, variables)

    total_latency = 0.0
    total_tokens = 0
    total_cost = 0.0
    attempts = 0
    last_response: Optional[LLMResponse] = None
    violations: list[str] = []

    current_user_prompt = user_prompt
    for attempt_idx in range(retries + 1):
        attempts = attempt_idx + 1
        request = LLMRequest(
            system_prompt=system_prompt,
            user_prompt=current_user_prompt,
            model=version.model_name or settings.active_model,
            temperature=version.temperature,
            max_tokens=version.max_tokens,
        )
        resp = provider.generate(request)
        total_latency += resp.latency_ms
        total_tokens += resp.total_tokens
        total_cost += resp.cost_estimate
        last_response = resp

        if resp.error:
            violations = [resp.error]
            break

        violations = validate_output_contract(
            resp.content,
            output_format=version.output_format,
            required_keywords=required_keywords,
            max_words=max_words,
        )
        if not violations:
            break

        if attempt_idx < retries:
            err_lines = "\n".join(f"- {v}" for v in violations)
            current_user_prompt = (
                f"{user_prompt}\n\n"
                f"Previous response:\n{resp.content}\n\n"
                f"Your previous response violated these output requirements:\n{err_lines}\n"
                "Return a corrected response that strictly satisfies every requirement."
            )

    if last_response is None:
        last_response = LLMResponse(content="", error="Harness did not execute.")

    merged_response = last_response.model_copy(update={
        "latency_ms": round(total_latency, 1),
        "total_tokens": total_tokens,
        "cost_estimate": round(total_cost, 6),
    })

    if enable_guardrails and not merged_response.error:
        out_guard = check_output_guardrails(
            merged_response.content,
            system_prompt=system_prompt,
            redact_pii=redact_pii,
            banned_terms=banned_terms,
        )
        if guardrail_report is not None:
            guardrail_report["output"] = out_guard
        merged_response = merged_response.model_copy(update={"content": out_guard["processed_output"]})
        if not out_guard["allowed"]:
            violations = list(violations) + [out_guard["blocked_reason"]]

    return {
        "response": merged_response,
        "attempts": attempts,
        "repaired": attempts > 1 and len(violations) == 0,
        "passed_contract": len(violations) == 0 and not merged_response.error,
        "validation_errors": violations,
        "input_sanitized": was_sanitized,
        "guardrail_report": guardrail_report,
    }


def evaluate_quality_gate(
    eval_results: list[EvaluationResult | dict],
    security_report: dict | None = None,
    min_avg_score: float = 75.0,
    min_format_score: float = 80.0,
    min_security_score: float = 80.0,
) -> dict:
    """
    Evaluate pass/fail release assertions over evaluation results and optional security audit.
    """
    normalized: list[EvaluationResult] = []
    for item in eval_results:
        if isinstance(item, EvaluationResult):
            normalized.append(item)
        else:
            from src.schemas import CriterionScore, ExecutionStatus
            raw_scores = item.get("criterion_scores", "[]")
            if isinstance(raw_scores, str):
                raw_scores = json.loads(raw_scores)
            normalized.append(EvaluationResult(
                test_case_id=item.get("test_case_id", ""),
                prompt_version_id=item.get("prompt_version_id", ""),
                experiment_id=item.get("experiment_id", ""),
                overall_score=float(item.get("overall_score", 0.0)),
                execution_status=ExecutionStatus(item.get("execution_status", "failed")),
                criterion_scores=[CriterionScore(**s) for s in raw_scores],
            ))

    agg = aggregate_results(normalized)
    avg_score = agg["avg_score"]
    format_avg = agg["criterion_averages"].get("format_compliance", 0.0)
    failed_count = agg["failed"]

    checks = [
        {
            "name": "Minimum Average Score",
            "actual": f"{avg_score:.1f}",
            "threshold": f">= {min_avg_score:.1f}",
            "passed": agg["success"] > 0 and avg_score >= min_avg_score,
        },
        {
            "name": "Minimum Format Compliance",
            "actual": f"{format_avg:.1f}",
            "threshold": f">= {min_format_score:.1f}",
            "passed": agg["success"] > 0 and format_avg >= min_format_score,
        },
        {
            "name": "Zero Failed Executions",
            "actual": str(failed_count),
            "threshold": "== 0",
            "passed": agg["total"] > 0 and failed_count == 0,
        },
    ]

    if security_report is not None:
        sec_score = float(security_report.get("robustness_score", 0.0))
        checks.append({
            "name": "Security Robustness",
            "actual": f"{sec_score:.1f}%",
            "threshold": f">= {min_security_score:.1f}%",
            "passed": sec_score >= min_security_score,
        })

    all_passed = all(c["passed"] for c in checks)
    return {
        "passed": all_passed,
        "status": "READY" if all_passed else "BLOCKED",
        "checks": checks,
    }


def main(argv: list[str] | None = None) -> int:
    """CLI regression harness runner for CI/CD quality gates."""
    parser = argparse.ArgumentParser(description="Shabd.Craft Prompt Regression Harness")
    parser.add_argument("--experiment", required=True, help="Experiment ID or exact name")
    parser.add_argument("--min-score", type=float, default=75.0, help="Minimum average score (0-100)")
    parser.add_argument("--min-format", type=float, default=80.0, help="Minimum format compliance (0-100)")
    parser.add_argument("--min-security", type=float, default=80.0, help="Minimum security robustness (0-100)")
    parser.add_argument("--db-path", default=settings.db_path, help="Path to SQLite database")
    args = parser.parse_args(argv)

    db = Database(args.db_path)
    exp = db.get_experiment(args.experiment)
    if not exp:
        exp = next((e for e in db.list_experiments(limit=500) if e["name"] == args.experiment), None)
    if not exp:
        print(f"Experiment not found: {args.experiment}", file=sys.stderr)
        return 1

    versions = db.get_prompt_versions(exp["id"])
    test_cases = db.get_test_cases(exp["id"])
    if not versions or not test_cases:
        print("Experiment must have at least one prompt version and one test case.", file=sys.stderr)
        return 1

    ver_data = versions[-1]
    few_shot_ex = [FewShotExample(**e) for e in json.loads(ver_data.get("few_shot_examples", "[]"))]
    version = PromptVersion(
        id=ver_data["id"],
        experiment_id=exp["id"],
        version_number=ver_data["version_number"],
        version_label=ver_data["version_label"],
        system_prompt=ver_data["system_prompt"],
        user_prompt_template=ver_data["user_prompt_template"],
        technique=PromptingTechnique(ver_data["technique"]),
        output_format=OutputFormat(ver_data["output_format"]),
        model_name=ver_data["model_name"],
        temperature=ver_data["temperature"],
        max_tokens=ver_data["max_tokens"],
        few_shot_examples=few_shot_ex,
    )

    tc_objects = [
        TestCase(id=tc["id"], input_data=tc["input_data"], expected_output=tc.get("expected_output", ""))
        for tc in test_cases
    ]
    eval_results = evaluate_batch(
        version=version,
        test_cases=tc_objects,
        experiment_id=exp["id"],
        weights=EvaluationWeights(),
        method=EvaluationMethod.RULE_BASED,
    )
    sec_report = run_security_audit(version)
    gate = evaluate_quality_gate(
        eval_results=eval_results,
        security_report=sec_report,
        min_avg_score=args.min_score,
        min_format_score=args.min_format,
        min_security_score=args.min_security,
    )

    print(f"Harness Gate: {gate['status']} ({exp['name']} v{ver_data['version_number']})")
    for chk in gate["checks"]:
        mark = "PASS" if chk["passed"] else "FAIL"
        print(f"  [{mark}] {chk['name']}: {chk['actual']} (required {chk['threshold']})")

    return 0 if gate["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

