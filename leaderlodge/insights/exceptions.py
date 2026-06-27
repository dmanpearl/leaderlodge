from __future__ import annotations


class InsightRateLimitExceeded(Exception):
    def __init__(
        self,
        *,
        scope: str,
        limit: int,
        window: str,
        retry_after_seconds: int,
        model_slug: str | None = None,
    ) -> None:
        self.scope = scope
        self.limit = limit
        self.window = window
        self.retry_after_seconds = retry_after_seconds
        self.model_slug = model_slug
        super().__init__(str(self))

    def __str__(self) -> str:
        if self.model_slug:
            return (
                f"Insight rate limit exceeded ({self.scope}, {self.window}, "
                f"model={self.model_slug}, limit={self.limit})."
            )
        return (
            f"Insight rate limit exceeded ({self.scope}, {self.window}, "
            f"limit={self.limit})."
        )
