"""
Shabd.Craft — Export Service

Export experiment results to CSV and JSON formats.
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any


def export_results_csv(results: list[dict], test_cases: list[dict] | None = None) -> str:
    """Export evaluation results to CSV string."""
    if not results:
        return ""

    tc_map = {}
    if test_cases:
        tc_map = {tc["id"]: tc for tc in test_cases}

    output = io.StringIO()
    writer = csv.writer(output)

    headers = [
        "evaluation_run_id", "test_case_id", "input_data", "expected_output", "generated_output",
        "overall_score", "execution_status", "evaluation_method",
        "accuracy", "relevance", "instruction_adherence", "clarity",
        "format_compliance", "latency_ms", "tokens_used", "is_demo",
    ]
    writer.writerow(headers)

    for r in results:
        tc = tc_map.get(r.get("test_case_id", ""), {})
        scores = _parse_criterion_scores(r.get("criterion_scores", "[]"))
        writer.writerow([
            r.get("evaluation_run_id", ""),
            r.get("test_case_id", ""),
            tc.get("input_data", "") or r.get("input_data_snapshot", ""),
            tc.get("expected_output", "") or r.get("expected_output_snapshot", ""),
            r.get("generated_output", ""),
            r.get("overall_score", 0),
            r.get("execution_status", ""),
            r.get("evaluation_method", ""),
            scores.get("accuracy", ""),
            scores.get("relevance", ""),
            scores.get("instruction_adherence", ""),
            scores.get("clarity", ""),
            scores.get("format_compliance", ""),
            r.get("latency_ms", 0),
            r.get("tokens_used", 0),
            r.get("is_demo", False),
        ])

    return output.getvalue()


def export_results_json(
    experiment: dict,
    versions: list[dict],
    test_cases: list[dict],
    results: list[dict],
    evaluation_runs: list[dict] | None = None,
) -> str:
    """Export complete experiment data as JSON."""
    data = {
        "experiment": _clean_for_export(experiment),
        "versions": [_clean_for_export(v) for v in versions],
        "test_cases": [_clean_for_export(tc) for tc in test_cases],
        "evaluation_results": [_clean_for_export(r) for r in results],
        "evaluation_runs": [_clean_for_export(run) for run in (evaluation_runs or [])],
    }
    return json.dumps(data, indent=2, default=str)


def export_experiment_summary_json(summary: dict) -> str:
    """Export experiment summary as JSON."""
    return json.dumps(summary, indent=2, default=str)


def parse_test_cases_csv(content: str, variable_mapping: dict[str, str] | None = None) -> tuple[list[dict], list[str]]:
    """
    Parse test cases from CSV content.
    Supports standard 'input_data'/'expected_output' columns, custom variable mapping,
    or multi-column headers packed into structured variable dictionaries.
    Returns (test_cases, errors).
    """
    test_cases = []
    errors = []

    try:
        reader = csv.DictReader(io.StringIO(content))
        fieldnames = reader.fieldnames or []
        expected_col = next((f for f in fieldnames if f.lower() in ("expected_output", "expected", "ground_truth", "target")), None)

        for i, row in enumerate(reader, 1):
            expected_val = (row.get(expected_col, "") if expected_col else "").strip()

            if variable_mapping:
                mapped = {var: str(row.get(col, "")).strip() for var, col in variable_mapping.items() if col in row}
                input_data = json.dumps(mapped) if len(mapped) > 1 else (next(iter(mapped.values())) if mapped else "")
            elif "input_data" in row or "input" in row:
                input_data = (row.get("input_data", "") or row.get("input", "")).strip()
            else:
                non_expected = [f for f in fieldnames if f != expected_col]
                if len(non_expected) == 1:
                    input_data = str(row.get(non_expected[0], "")).strip()
                elif len(non_expected) > 1:
                    input_data = json.dumps({col: str(row.get(col, "")).strip() for col in non_expected})
                else:
                    errors.append(f"Row {i}: Missing input data.")
                    continue

            if not input_data.strip():
                errors.append(f"Row {i}: Empty input data.")
                continue

            test_cases.append({
                "input_data": input_data.strip(),
                "expected_output": expected_val,
            })

        if not test_cases and not errors:
            errors.append("No valid test cases found in CSV.")

    except Exception as e:
        errors.append(f"Failed to parse CSV: {str(e)}")

    return test_cases, errors


def parse_test_cases_json(content: str) -> tuple[list[dict], list[str]]:
    """
    Parse test cases from JSON content.
    Returns (test_cases, errors).
    """
    test_cases = []
    errors = []

    try:
        data = json.loads(content)
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict) and "test_cases" in data:
            items = data["test_cases"]
        else:
            errors.append("JSON must be an array or contain a 'test_cases' array.")
            return test_cases, errors

        for i, item in enumerate(items, 1):
            if not isinstance(item, dict):
                errors.append(f"Item {i}: Not a valid object.")
                continue

            input_data = item.get("input_data", "") or item.get("input", "")
            if not input_data.strip():
                errors.append(f"Item {i}: Missing or empty 'input_data'.")
                continue

            test_cases.append({
                "input_data": input_data.strip(),
                "expected_output": (item.get("expected_output", "") or item.get("expected", "")).strip(),
            })

    except json.JSONDecodeError as e:
        errors.append(f"Invalid JSON: {str(e)}")

    return test_cases, errors


def _parse_criterion_scores(scores_raw) -> dict[str, float]:
    """Parse criterion scores from stored format."""
    if isinstance(scores_raw, str):
        try:
            scores = json.loads(scores_raw)
        except json.JSONDecodeError:
            return {}
    else:
        scores = scores_raw

    result = {}
    for s in scores:
        if isinstance(s, dict):
            result[s.get("name", "")] = s.get("score", 0)
    return result


def _clean_for_export(data: dict) -> dict:
    """Clean data for export by parsing JSON strings."""
    cleaned = dict(data)
    for key in ["criterion_scores", "weaknesses", "suggestions", "variables",
                 "few_shot_examples", "metadata", "eval_criteria"]:
        if key in cleaned and isinstance(cleaned[key], str):
            try:
                cleaned[key] = json.loads(cleaned[key])
            except (json.JSONDecodeError, TypeError):
                pass
    return cleaned


def generate_production_code(
    system_prompt: str,
    user_prompt: str,
    model: str = "gpt-3.5-turbo",
    temperature: float = 0.7,
    max_tokens: int = 1024,
    include_harness: bool = False,
    output_format: str = "text",
    required_json_keys: list[str] | None = None,
) -> dict[str, str]:
    """
    Generate ready-to-run code snippets (OpenAI SDK, LangChain, cURL)
    for a crafted prompt, with optional production Auto-Repair Harness wrapper.
    """
    resolved_model = "gpt-3.5-turbo" if model == "demo-simulator" else (model or "gpt-3.5-turbo")
    sys_lit = json.dumps(system_prompt or "You are a helpful assistant.")
    usr_lit = json.dumps(user_prompt or "")

    if include_harness:
        keys_check = ""
        if output_format == "json" and required_json_keys:
            keys_lit = json.dumps(required_json_keys)
            keys_check = f"""
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            missing = [k for k in {keys_lit} if k not in parsed]
            if missing:
                violations.append(f"Missing required JSON keys: {{', '.join(missing)}}")
        else:
            violations.append("Output is not a valid JSON dictionary")
"""
        elif output_format == "json":
            keys_check = """
        json.loads(text)
"""

        openai_python = f"""import json
import os
import re
import time
from openai import OpenAI

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

MODEL = {json.dumps(resolved_model)}
SYSTEM_PROMPT = {sys_lit}
USER_TEMPLATE = {usr_lit}

def sanitize_untrusted_input(text: str) -> str:
    \"\"\"Pre-execution guardrail: strip boundary tags and mask credentials.\"\"\"
    cleaned = re.sub(r"</\\s*(user_input|context|system)\\s*>", "[tag_removed]", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"\\bsk-(?:proj-)?[A-Za-z0-9_-]{{16,}}\\b", "[SECRET_REDACTED]", cleaned)
    return cleaned

def validate_contract(text: str) -> list[str]:
    \"\"\"Deterministic output validation.\"\"\"
    violations = []
    try:{keys_check if keys_check else ' pass'}
    except json.JSONDecodeError as e:
        violations.append(f"Invalid JSON: {{e.msg}}")
    return violations

def execute_with_harness(input_data: str, max_retries: int = 2) -> dict:
    \"\"\"Execute prompt with pre-guardrails, contract enforcement, and self-repair retries.\"\"\"
    sanitized = sanitize_untrusted_input(input_data)
    prompt = USER_TEMPLATE.replace("{{{{input}}}}", sanitized)

    current_prompt = prompt
    for attempt in range(max_retries + 1):
        response = client.chat.completions.create(
            model=MODEL,
            temperature={temperature},
            max_tokens={max_tokens},
            messages=[
                {{"role": "system", "content": SYSTEM_PROMPT}},
                {{"role": "user", "content": current_prompt}},
            ],
        )
        content = response.choices[0].message.content or ""
        violations = validate_contract(content)

        if not violations:
            return {{"content": content, "attempts": attempt + 1, "passed_contract": True}}

        if attempt < max_retries:
            err_feedback = "\\n".join(f"- {{v}}" for v in violations)
            current_prompt = (
                f"{{prompt}}\\n\\n"
                f"Previous response:\\n{{content}}\\n\\n"
                f"Violations detected:\\n{{err_feedback}}\\n"
                "Return a corrected response strictly satisfying all requirements."
            )
            time.sleep(0.5)

    return {{"content": content, "attempts": max_retries + 1, "passed_contract": False, "violations": violations}}

if __name__ == "__main__":
    result = execute_with_harness("Sample test data")
    print(f"Passed Contract: {{result['passed_contract']}} (Attempts: {{result['attempts']}})")
    print("Response:\\n", result["content"])
"""
    else:
        openai_python = (
            "import os\n"
            "from openai import OpenAI\n\n"
            "client = OpenAI(api_key=os.environ.get(\"OPENAI_API_KEY\"))\n\n"
            f"system_prompt = {sys_lit}\n"
            f"user_prompt = {usr_lit}\n\n"
            "response = client.chat.completions.create(\n"
            f"    model={json.dumps(resolved_model)},\n"
            f"    temperature={temperature},\n"
            f"    max_tokens={max_tokens},\n"
            "    messages=[\n"
            "        {\"role\": \"system\", \"content\": system_prompt},\n"
            "        {\"role\": \"user\", \"content\": user_prompt},\n"
            "    ],\n"
            ")\n\n"
            "print(response.choices[0].message.content)\n"
        )

    langchain_python = (
        "from langchain_openai import ChatOpenAI\n"
        "from langchain_core.messages import SystemMessage, HumanMessage\n\n"
        "llm = ChatOpenAI(\n"
        f"    model={json.dumps(resolved_model)},\n"
        f"    temperature={temperature},\n"
        f"    max_tokens={max_tokens},\n"
        ")\n\n"
        "messages = [\n"
        f"    SystemMessage(content={sys_lit}),\n"
        f"    HumanMessage(content={usr_lit}),\n"
        "]\n\n"
        "result = llm.invoke(messages)\n"
        "print(result.content)\n"
    )

    payload = json.dumps({
        "model": resolved_model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system_prompt or "You are a helpful assistant."},
            {"role": "user", "content": user_prompt or ""},
        ],
    }, indent=2)

    curl_cmd = (
        "curl https://api.openai.com/v1/chat/completions \\\n"
        "  -H \"Content-Type: application/json\" \\\n"
        "  -H \"Authorization: Bearer $OPENAI_API_KEY\" \\\n"
        f"  -d '{payload}'"
    )

    return {
        "openai_python": openai_python,
        "langchain_python": langchain_python,
        "curl": curl_cmd,
    }
