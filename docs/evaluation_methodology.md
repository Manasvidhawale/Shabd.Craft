# Shabd.Craft — Evaluation Methodology

## Overview

Shabd.Craft uses a two-tier evaluation approach designed to be both objectively verifiable (rule-based) and semantically rich (LLM-as-a-Judge). This document explains the design decisions, limitations, and correct interpretation of evaluation scores.

---

## Evaluation Criteria

Every evaluation in Shabd.Craft uses the same five criteria, each scored 0–100:

| Criterion | Description |
|---|---|
| **Accuracy** | Factual correctness; alignment with expected output when available |
| **Relevance** | How well the response addresses the specific input |
| **Instruction Adherence** | How closely the response follows the prompt's instructions |
| **Clarity** | Readability, completeness, and logical organization |
| **Format Compliance** | Whether the output matches the required format (JSON, Markdown, etc.) |

---

## Weighted Scoring

```
Overall Score = Σ (Criterion Score × Normalized Criterion Weight)
```

Weights are normalized to sum to 1.0 before use:

```
normalized_weight_i = raw_weight_i / Σ raw_weights
```

**Example:**

| Criterion | Score | Weight | Contribution |
|---|---|---|---|
| Accuracy | 80 | 0.25 | 20.0 |
| Relevance | 90 | 0.20 | 18.0 |
| Instruction Adherence | 85 | 0.25 | 21.25 |
| Clarity | 75 | 0.15 | 11.25 |
| Format Compliance | 100 | 0.15 | 15.0 |
| **Overall** | | | **85.5** |

---

## Tier 1: Rule-Based Evaluation

Rule-based evaluation uses deterministic, objective checks. Results are identical for the same input regardless of when the evaluation is run.

### Checks implemented

| Check | Condition | Score |
|---|---|---|
| Empty response | Output is blank | 0 (all criteria) |
| JSON validity | Valid parseable JSON | 100; embedded JSON: 50; invalid: 20 |
| Required JSON fields | All fields present | 60 if missing |
| Keyword presence | Fraction of keywords found | Proportional to found/total |
| Word count | Within max_words limit | Proportional penalty for overage |
| Exact match | Output == expected (case-insensitive) | 100 |
| Content overlap | Word overlap with expected | Proportional to overlap ratio |

### Limitations

- Exact matching is not appropriate for open-ended generation tasks.
- Word overlap is a weak proxy for semantic similarity.
- Rule-based evaluation cannot assess reasoning quality, tone, or nuance.
- JSON structure validation does not verify semantic correctness of values.

---

## Tier 2: LLM-as-a-Judge

The LLM judge uses a separate model call with an explicit scoring rubric to evaluate the response quality against each criterion.

### Judge prompt design

The judge receives:
- Original task instructions (system + user prompt)
- Test input
- Expected output (if provided) — explicitly labeled as a reference answer
- Actual model output
- Evaluation criteria with 0–100 scoring definitions

The judge is instructed to:
- Be critical and evidence-based.
- Not reward longer answers.
- Compare against the reference when available.
- Use rubric-based reasoning when no reference is available.

### Response validation

The judge must return valid JSON with:
```json
{
  "criterion_scores": [
    {"name": "accuracy", "score": 80, "explanation": "..."},
    ...
  ],
  "overall_score": 82,
  "weaknesses": ["..."],
  "suggestions": ["..."]
}
```

- Score values are clamped to [0, 100].
- Malformed responses trigger bounded retries (up to 2 additional attempts).
- On persistent failure, a fallback with score=0 and a clear error message is returned.

### Temperature

The judge runs at temperature=0.1 for maximum consistency.

---

## Interpretation Guidelines

### What scores mean

| Score Range | Interpretation |
|---|---|
| 85–100 | Strong performance; likely meets task requirements |
| 70–84 | Adequate; may have specific weaknesses |
| 50–69 | Notable issues; prompt likely needs refinement |
| Below 50 | Significant problems; review prompt and test cases |

### What scores do NOT mean

- A score of 85 does not guarantee the response is factually correct without a reference.
- An improvement from 70 to 80 is not necessarily statistically significant on a small test set.
- LLM judge scores can vary between runs (typically ±5–15 points for equivalent outputs).
- Demo mode scores are deterministic but do not reflect actual model quality.

---

## Correct Comparison Practices

1. **Use identical test cases** when comparing two prompt versions.
2. **Use identical weights** within a comparison session.
3. **Record the model and settings** used for each evaluation run.
4. **Report failures separately** — a failed execution is not a low-quality answer.
5. **Note sample size** — comparisons on fewer than 5 test cases are unreliable.
6. **Treat judge variability honestly** — re-run evaluations if a result seems unexpected.

---

## Demo Mode Evaluation

In demo mode, all criterion scores are generated deterministically using an MD5 hash of the output content as a random seed. This means:

- The same output always produces the same demo score.
- Different outputs produce different (but arbitrary) scores.
- Demo scores have no relationship to actual model quality.
- All demo results are clearly labeled with `[DEMO]` tags and `is_demo=True` flags.

---

## Known Limitations

1. LLM-as-a-Judge introduces a second model's bias and can be gamed by verbose outputs.
2. Rule-based evaluation cannot handle semantic equivalence (e.g., "Yes" vs "Affirmative").
3. Weighted scoring collapses multi-dimensional quality into a single number, losing nuance.
4. Evaluation results from different models or configurations are not directly comparable.
5. No repeatability mechanism (multiple runs and averaging) is currently implemented.
6. The application does not compute statistical significance for score differences.

---

## References

- Chang et al. (2023). "A Survey on Evaluation of Large Language Models."
- Zheng et al. (2023). "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena."
- Guo et al. (2023). "Evaluating Large Language Models: A Comprehensive Survey."
