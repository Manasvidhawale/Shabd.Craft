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

    def _demo_json_response(self, prompt: str, rng: random.Random) -> str:
        data = {
            "result": "Demo analysis output",
            "key_points": [
                "First identified point from demo analysis",
                "Second identified point from demo analysis",
                "Third identified point from demo analysis",
            ],
            "confidence": round(rng.uniform(0.75, 0.95), 2),
            "category": rng.choice(["positive", "neutral", "negative"]),
            "_note": "SIMULATED — This is a demo response, not from a real LLM.",
        }
        return json.dumps(data, indent=2)

    def _demo_summary_response(self, rng: random.Random) -> str:
        summaries = [
            "[DEMO] The text discusses three main areas: customer satisfaction with "
            "product quality, concerns about delivery timelines, and suggestions for "
            "improved communication channels. Key issues include delayed shipments "
            "and inconsistent packaging quality.",
            "[DEMO] Summary: The feedback highlights strong product performance but "
            "identifies service bottlenecks. Users appreciate the core functionality "
            "while requesting better documentation and faster response times.",
            "[DEMO] The primary themes are: (1) positive reception of new features, "
            "(2) frustration with onboarding complexity, and (3) desire for more "
            "customization options. Overall sentiment is cautiously optimistic.",
        ]
        return rng.choice(summaries)

    def _demo_sentiment_response(self, rng: random.Random) -> str:
        sentiments = [
            "[DEMO] Sentiment: Positive (Score: 0.78)\nThe text expresses satisfaction "
            "with the product while noting minor areas for improvement.",
            "[DEMO] Sentiment: Mixed (Score: 0.52)\nThe text contains both positive "
            "feedback about features and negative feedback about support experience.",
            "[DEMO] Sentiment: Negative (Score: 0.31)\nThe text primarily expresses "
            "dissatisfaction with service delays and communication gaps.",
        ]
        return rng.choice(sentiments)

    def _demo_classification_response(self, rng: random.Random) -> str:
        return (
            "[DEMO] Classification Result:\n"
            f"- Primary Category: {rng.choice(['Support Request', 'Feature Request', 'Bug Report', 'General Inquiry'])}\n"
            f"- Confidence: {rng.uniform(0.7, 0.95):.2f}\n"
            f"- Priority: {rng.choice(['High', 'Medium', 'Low'])}\n"
            "Note: This is a simulated classification, not from a real LLM."
        )

    def _demo_extraction_response(self, rng: random.Random) -> str:
        return (
            "[DEMO] Extracted Information:\n"
            "- Entity 1: Product Team (Organization)\n"
            "- Entity 2: Q3 2024 (Date Reference)\n"
            "- Entity 3: Customer Portal (System)\n"
            f"- Key metric: {rng.randint(80, 99)}% accuracy target\n"
            "Note: This is a simulated extraction, not from a real LLM."
        )

    def _demo_email_response(self, rng: random.Random) -> str:
        return (
            "[DEMO] Subject: Follow-up on Your Recent Inquiry\n\n"
            "Dear Valued Customer,\n\n"
            "Thank you for reaching out to us. We have reviewed your request and "
            "would like to provide the following update:\n\n"
            "Your case has been assigned to our specialist team and we expect to "
            "have a resolution within 2-3 business days.\n\n"
            "Please don't hesitate to contact us if you need any further assistance.\n\n"
            "Best regards,\nSupport Team\n\n"
            "[Note: This is a simulated email, not generated by a real LLM.]"
        )

    def _demo_qa_response(self, rng: random.Random) -> str:
        return (
            "[DEMO] Based on the provided context, the answer is:\n\n"
            "The process involves three key steps: initial assessment, implementation "
            "planning, and iterative refinement. Each step builds on the previous one "
            "to ensure comprehensive coverage of all requirements.\n\n"
            "Note: This is a simulated answer, not from a real LLM."
        )

    def _demo_general_response(self, rng: random.Random) -> str:
        responses = [
            "[DEMO] This is a simulated response generated by Shabd.Craft's demo mode. "
            "In live mode with a configured API key, this would contain the actual "
            "LLM-generated output based on your prompt. The demo response is designed "
            "to help you explore the platform's features without requiring API access.",
            "[DEMO] Demo response: The analysis indicates several key findings that "
            "would be relevant to the task described in your prompt. In production mode, "
            "this content would be generated by the configured LLM provider.",
            "[DEMO] Simulated output for your prompt. The platform would generate a "
            "real response using the selected model and parameters when connected to "
            "a live API provider.",
        ]
        return rng.choice(responses)
