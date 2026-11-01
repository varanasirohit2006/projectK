"""Execution budgets for cost, source count, retries, and duration."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


class BudgetExceeded(RuntimeError):
    """Raised when a run exceeds an explicit user budget."""


@dataclass
class BudgetTracker:
    max_cost_usd: float
    max_duration_seconds: int
    max_sources: int
    max_retries: int = 3
    started_at: float = field(default_factory=time.monotonic)
    cost_usd: float = 0.0
    source_count: int = 0
    retries: int = 0

    def check(self) -> None:
        if self.cost_usd > self.max_cost_usd:
            raise BudgetExceeded("Configured cost budget was exceeded")
        if time.monotonic() - self.started_at > self.max_duration_seconds:
            raise BudgetExceeded("Configured duration budget was exceeded")
        if self.source_count > self.max_sources:
            raise BudgetExceeded("Configured source budget was exceeded")
        if self.retries > self.max_retries:
            raise BudgetExceeded("Configured retry budget was exceeded")

    def record(self, *, cost_usd: float = 0.0, sources: int = 0, retries: int = 0) -> None:
        self.cost_usd += cost_usd
        self.source_count += sources
        self.retries += retries
        self.check()
