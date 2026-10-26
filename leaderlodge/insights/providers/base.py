from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict
    # Opaque Gemini thought signature, base64. Echoed on the next tool turn.
    thought_signature: str = ""


@dataclass(frozen=True)
class InsightCompletion:
    text: str
    input_tokens: int
    output_tokens: int
    model_api_name: str
    provider: str
    tool_calls: tuple[ToolCall, ...] = field(default_factory=tuple)


class InsightProviderError(RuntimeError):
    pass
