"""
LLM service abstraction.

Every other part of the codebase (agent, tutor, evaluator) calls
`llm_service.complete(prompt, ...)` and never touches a provider SDK
directly. This is what makes swapping mock -> real a one-line config
change (LLM_PROVIDER in .env) instead of a rewrite.

Mock mode returns deterministic, plausible-looking responses so you can
fully demo the agent loop, UI, and dashboard before you ever add a paid
API key.
"""
import json
import random
import re
from abc import ABC, abstractmethod

from app.config import settings


class LLMProvider(ABC):
    @abstractmethod
    def complete(self, prompt: str, system: str = "", max_tokens: int = 1000) -> str:
        ...


class MockLLMProvider(LLMProvider):
    """
    Deterministic-ish canned responses keyed off keywords in the prompt,
    so different tool calls (explain / evaluate / question-gen) return
    plausibly different mock output instead of one generic string.
    """

    def complete(self, prompt: str, system: str = "", max_tokens: int = 1000) -> str:
        lowered = prompt.lower()

        if "generate a quiz question" in lowered or "generate_quiz" in lowered:
            return (
                "Question: Explain why word embeddings place semantically "
                "similar words closer together in vector space.\n"
                "Difficulty: medium"
            )

        if "evaluate" in lowered and "answer" in lowered:
            return (
                "Score: 7.5/10\n"
                "Covered: basic definition, correct core mechanism\n"
                "Missing: relationship to vector distance / cosine similarity\n"
                "Misconception: none detected\n"
                "Feedback: Good grasp of the fundamentals. Review how "
                "distance metrics quantify semantic similarity."
            )

        if "explain" in lowered and "beginner-friendly" in lowered:
            m = re.search(r"concept '([^']+)'", prompt, re.IGNORECASE)
            concept = m.group(1) if m else "this concept"
            return (
                f"[MOCK EXPLANATION] {concept.capitalize()} is a building block you will use again and again. "
                f"Think of it like learning the alphabet before writing sentences: get comfortable with {concept} "
                f"first and later topics get much easier. With a real LLM key this becomes a tailored explanation "
                f"drawn from your uploaded material."
            )

        if "multiple-choice" in lowered and "respond only with json" in lowered:
            m = re.search(r"concept:\s*(.+)", prompt, re.IGNORECASE)
            concept = m.group(1).strip() if m else "this concept"
            correct = f"The correct, standard definition of {concept}"
            return json.dumps({
                "question": f"[MOCK] Which statement best describes {concept}?",
                "options": [correct, f"A common misconception about {concept}",
                            f"A concept unrelated to {concept}", f"An incomplete definition of {concept}"],
                "correct_answer": correct,
            })

        if "explain" in lowered or "teach" in lowered:
            return (
                "Think of this concept as a way of organizing information "
                "so a computer can compare meaning numerically rather than "
                "just matching exact words. [MOCK EXPLANATION — replace "
                "with real LLM output once an API key is configured.]"
            )

        if "study plan" in lowered:
            return (
                "Recommended order: 1) Reinforce prerequisite fundamentals "
                "2) Targeted quiz on weakest topic 3) New concept "
                "introduction 4) Spaced revision of yesterday's material."
            )

        if "respond only with json" in lowered and "prerequisite" in lowered:
            # Mock prerequisite inference: naive linear chain based on the
            # order concepts appear in the prompt, wrapped as JSON so the
            # real parsing path in material_tools.py gets exercised even
            # without a real LLM.
            match = re.search(r"concepts:\s*(.+)", prompt, re.IGNORECASE)
            names = [n.strip() for n in match.group(1).split(",")] if match else []
            result = {names[0]: []} if names else {}
            for i in range(1, len(names)):
                result[names[i]] = [names[i - 1]]
            return json.dumps(result)

        return "[MOCK RESPONSE] " + prompt[:120]


class AnthropicProvider(LLMProvider):
    def __init__(self):
        # Imported lazily so the package isn't required in mock-only dev.
        import anthropic
        self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    def complete(self, prompt: str, system: str = "", max_tokens: int = 1000) -> str:
        response = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=max_tokens,
            system=system or "You are a helpful, precise AI tutor.",
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(
            block.text for block in response.content if block.type == "text"
        )


class OpenAIProvider(LLMProvider):
    def __init__(self):
        import openai
        self.client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)

    def complete(self, prompt: str, system: str = "", max_tokens: int = 1000) -> str:
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system or "You are a helpful, precise AI tutor."},
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content


def get_llm_provider() -> LLMProvider:
    if settings.LLM_PROVIDER == "anthropic":
        return AnthropicProvider()
    if settings.LLM_PROVIDER == "openai":
        return OpenAIProvider()
    return MockLLMProvider()


llm_service = get_llm_provider()
