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
        "test_case_id", "input_data", "expected_output", "generated_output",
        "overall_score", "execution_status", "evaluation_method",
        "accuracy", "relevance", "instruction_adherence", "clarity",
        "format_compliance", "latency_ms", "tokens_used", "is_demo",
    ]
    writer.writerow(headers)

    for r in results:
        tc = tc_map.get(r.get("test_case_id", ""), {})
        scores = _parse_criterion_scores(r.get("criterion_scores", "[]"))
        writer.writerow([
            r.get("test_case_id", ""),
            tc.get("input_data", ""),
            tc.get("expected_output", ""),
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
) -> str:
    """Export complete experiment data as JSON."""
    data = {
        "experiment": _clean_for_export(experiment),
        "versions": [_clean_for_export(v) for v in versions],
        "test_cases": [_clean_for_export(tc) for tc in test_cases],
        "evaluation_results": [_clean_for_export(r) for r in results],
    }
    return json.dumps(data, indent=2, default=str)


def export_experiment_summary_json(summary: dict) -> str:
    """Export experiment summary as JSON."""
    return json.dumps(summary, indent=2, default=str)


def parse_test_cases_csv(content: str) -> tuple[list[dict], list[str]]:
    """
    Parse test cases from CSV content.
    Returns (test_cases, errors).
    """
    test_cases = []
    errors = []

    try:
        reader = csv.DictReader(io.StringIO(content))
        for i, row in enumerate(reader, 1):
            if "input_data" not in row and "input" not in row:
                errors.append(f"Row {i}: Missing 'input_data' or 'input' column.")
                continue

            input_data = row.get("input_data", "") or row.get("input", "")
            if not input_data.strip():
                errors.append(f"Row {i}: Empty input data.")
                continue

            test_cases.append({
                "input_data": input_data.strip(),
                "expected_output": (row.get("expected_output", "") or row.get("expected", "")).strip(),
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
) -> dict[str, str]:
    """
    Generate ready-to-run code snippets (OpenAI SDK, LangChain, cURL)
    for a crafted prompt.
    """
    resolved_model = "gpt-3.5-turbo" if model == "demo-simulator" else (model or "gpt-3.5-turbo")
    sys_lit = json.dumps(system_prompt or "You are a helpful assistant.")
    usr_lit = json.dumps(user_prompt or "")

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
