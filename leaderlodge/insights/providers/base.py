from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InsightCompletion:
    text: str
    input_tokens: int
    output_tokens: int
    model_api_name: str
    provider: str


class InsightProviderError(RuntimeError):
    pass
