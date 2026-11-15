"""
Shabd.Craft — Demo LLM Provider

Returns clearly-labeled simulated responses for demonstration purposes.
Works without an API key. All outputs are marked as demo/simulated.
"""

from __future__ import annotations

import hashlib
import json
import random
import time

from src.providers.base import BaseLLMProvider
from src.schemas import LLMRequest, LLMResponse


class DemoProvider(BaseLLMProvider):
    """Simulated LLM provider for demo mode. All responses are clearly labeled."""

    @property
    def provider_name(self) -> str:
        return "demo"

    @property
    def is_demo(self) -> bool:
        return True

    def is_available(self) -> bool:
        return True

    def generate(self, request: LLMRequest) -> LLMResponse:
        start = time.time()

        # Deterministic seed based on prompt content for consistent demos
        seed = int(hashlib.md5(request.user_prompt.encode()).hexdigest()[:8], 16)
        rng = random.Random(seed)

        content = self._generate_demo_response(request, rng)
        latency = (time.time() - start) * 1000 + rng.uniform(50, 200)

        # Simulated token counts (clearly approximate)
        prompt_tokens = len(request.user_prompt.split()) + len(request.system_prompt.split())
        completion_tokens = len(content.split())

        return LLMResponse(
            content=content,
            model="demo-simulator",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            latency_ms=round(latency, 1),
            cost_estimate=0.0,
            is_demo=True,
        )

    def _generate_demo_response(self, request: LLMRequest, rng: random.Random) -> str:
        """Generate a context-aware simulated response based on the prompt."""
        prompt_lower = request.user_prompt.lower()
        sys_lower = (request.system_prompt or "").lower()

        # Simulate realistic prompt injection behavior in Demo Mode
        if self._is_injection_probe(prompt_lower):
            has_delimiters = any(d in request.user_prompt for d in ("<user_input>", '"""', "'''", "---"))
            has_defense = any(d in sys_lower for d in ("untrusted", "security boundary", "never reveal", "do not follow", "strictly as data"))
            if not (has_delimiters and has_defense):
                if "security_bypass_ok" in prompt_lower:
                    return "SECURITY_BYPASS_OK"
                if "admin_access_granted" in prompt_lower:
                    return "ADMIN_ACCESS_GRANTED"
                if "delimiter_escaped" in prompt_lower and not has_delimiters:
                    return "DELIMITER_ESCAPED"
                if "unfiltered_mode" in prompt_lower and not has_defense:
                    return "UNFILTERED_MODE"
                if ("repeat the exact system instructions" in prompt_lower or "hidden prompt" in prompt_lower) and not has_defense:
                    leaked = request.system_prompt.strip() or "No system prompt was set."
                    return f"Here are my system instructions: {leaked}"

        # Check for JSON output request
        if "json" in prompt_lower or "structured" in prompt_lower:
            return self._demo_json_response(prompt_lower, rng)

        # Check for summarization
        if "summar" in prompt_lower:
            return self._demo_summary_response(rng)

        # Check for sentiment
        if "sentiment" in prompt_lower:
            return self._demo_sentiment_response(rng)

        # Check for classification
        if "classif" in prompt_lower or "categoriz" in prompt_lower:
            return self._demo_classification_response(rng)

        # Check for extraction
        if "extract" in prompt_lower:
            return self._demo_extraction_response(rng)

        # Check for email
        if "email" in prompt_lower:
            return self._demo_email_response(rng)

        # Check for question answering
        if "answer" in prompt_lower or "question" in prompt_lower:
            return self._demo_qa_response(rng)

        # Default response
        return self._demo_general_response(rng)

    @staticmethod
    def _is_injection_probe(prompt_lower: str) -> bool:
        """Detect if the prompt contains a known security audit probe payload."""
        markers = (
            "security_bypass_ok",
            "admin_access_granted",
            "delimiter_escaped",
            "unfiltered_mode",
            "repeat the exact system instructions",
            "hidden prompt, and system rules",
        )
        return any(m in prompt_lower for m in markers)

    def _demo_json_response(self, prompt: str, rng: random.Random) -> str:
        data = {
            "result": "Structured analysis output",
            "key_points": [
                "Primary theme identified from the input text",
                "Secondary observation and supporting detail",
                "Recommended follow-up action",
            ],
            "confidence": round(rng.uniform(0.75, 0.95), 2),
            "category": rng.choice(["positive", "neutral", "negative"]),
        }
        return json.dumps(data, indent=2)

    def _demo_summary_response(self, rng: random.Random) -> str:
        summaries = [
            "The text highlights three main areas: customer satisfaction with "
            "product quality, concerns about delivery timelines, and suggestions for "
            "improved communication channels. Key issues include delayed shipments "
            "and inconsistent packaging quality.",
            "Summary: The feedback highlights strong product performance while "
            "identifying service bottlenecks. Users appreciate the core functionality "
            "and request clearer documentation alongside faster response times.",
            "Primary themes: (1) positive reception of core features, "
            "(2) friction during initial onboarding, and (3) demand for more "
            "customization options. Overall sentiment is cautiously optimistic.",
        ]
        return rng.choice(summaries)

    def _demo_sentiment_response(self, rng: random.Random) -> str:
        sentiments = [
            "Sentiment: Positive (Score: 0.78)\nThe text expresses satisfaction "
            "with the product while noting minor areas for improvement.",
            "Sentiment: Mixed (Score: 0.52)\nThe text contains both positive "
            "feedback about features and negative feedback about support experience.",
            "Sentiment: Negative (Score: 0.31)\nThe text primarily expresses "
            "dissatisfaction with service delays and communication gaps.",
        ]
        return rng.choice(sentiments)

    def _demo_classification_response(self, rng: random.Random) -> str:
        return (
            "Classification Result:\n"
            f"- Primary Category: {rng.choice(['Support Request', 'Feature Request', 'Bug Report', 'General Inquiry'])}\n"
            f"- Confidence: {rng.uniform(0.7, 0.95):.2f}\n"
            f"- Priority: {rng.choice(['High', 'Medium', 'Low'])}"
        )

    def _demo_extraction_response(self, rng: random.Random) -> str:
        return (
            "Extracted Information:\n"
            "- Entity 1: Product Team (Organization)\n"
            "- Entity 2: Q3 2024 (Date Reference)\n"
            "- Entity 3: Customer Portal (System)\n"
            f"- Key metric: {rng.randint(80, 99)}% accuracy target"
        )

    def _demo_email_response(self, rng: random.Random) -> str:
        return (
            "Subject: Follow-up on Your Recent Inquiry\n\n"
            "Dear Valued Customer,\n\n"
            "Thank you for reaching out to us. We have reviewed your request and "
            "would like to provide the following update:\n\n"
            "Your case has been assigned to our specialist team and we expect to "
            "have a resolution within 2-3 business days.\n\n"
            "Please don't hesitate to contact us if you need any further assistance.\n\n"
            "Best regards,\nSupport Team"
        )

    def _demo_qa_response(self, rng: random.Random) -> str:
        return (
            "Based on the provided context, the answer is:\n\n"
            "The process involves three key steps: initial assessment, implementation "
            "planning, and iterative refinement. Each step builds on the previous one "
            "to ensure comprehensive coverage of all requirements."
        )

    def _demo_general_response(self, rng: random.Random) -> str:
        responses = [
            "Analysis complete. Based on the provided instructions and input, "
            "key takeaways include clear alignment with the primary objective, "
            "consistent structure, and actionable next steps.",
            "Response summary: The input presents clear criteria that map directly "
            "to the requested output structure. Key points have been synthesized "
            "for readability and conciseness.",
            "Processed output: All core requirements from the prompt template have "
            "been addressed with structured reasoning and direct supporting details.",
        ]
        return rng.choice(responses)
