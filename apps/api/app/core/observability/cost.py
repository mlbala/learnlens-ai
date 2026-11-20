"""Versioned estimated cost calculation — never claim live vendor rates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Explicit placeholder schedule. Operators must replace with verified vendor pricing
# before treating estimates as budget truth. Version bumps when the formula changes.
COST_ESTIMATE_VERSION = "v0-placeholder-not-live-rates"
COST_ESTIMATE_DISCLAIMER = (
    "Estimated cost only — not live vendor pricing. "
    f"Calculation version {COST_ESTIMATE_VERSION}. "
    "Do not use for billing or invoicing."
)


@dataclass(frozen=True, slots=True)
class CostEstimate:
    estimate_usd: float
    estimate_version: str
    is_estimate: bool
    tokens_in: int
    tokens_out: int
    provider: str
    model: str
    disclaimer: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "estimate_usd": self.estimate_usd,
            "estimate_version": self.estimate_version,
            "is_estimate": self.is_estimate,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "provider": self.provider,
            "model": self.model,
            "disclaimer": self.disclaimer,
        }


# Placeholder micro-USD per 1K tokens — clearly not vendor rates.
# Fake provider stays at 0 so offline tests never imply spend.
_PLACEHOLDER_PER_1K: dict[str, tuple[float, float]] = {
    "fake": (0.0, 0.0),
    "openai": (0.001, 0.002),
    "gemini": (0.0008, 0.0016),
    "deepseek": (0.0005, 0.001),
}


def estimate_provider_cost(
    *,
    provider: str,
    model: str,
    token_in: int | None,
    token_out: int | None,
) -> CostEstimate:
    """
    Compute a clearly labeled estimate from placeholder rates.

    Missing token counts → 0 estimate (still labeled). Never invent token usage.
    """
    tin = max(0, int(token_in or 0))
    tout = max(0, int(token_out or 0))
    key = provider.strip().lower()
    in_rate, out_rate = _PLACEHOLDER_PER_1K.get(key, (0.001, 0.002))
    usd = (tin / 1000.0) * in_rate + (tout / 1000.0) * out_rate
    return CostEstimate(
        estimate_usd=round(usd, 8),
        estimate_version=COST_ESTIMATE_VERSION,
        is_estimate=True,
        tokens_in=tin,
        tokens_out=tout,
        provider=provider,
        model=model,
        disclaimer=COST_ESTIMATE_DISCLAIMER,
    )
