from __future__ import annotations

from typing import Any

from app.domain.plans import Plan


def select_price_snapshot(plan_or_prices: Plan | list[dict[str, Any]], billing_period: str) -> dict[str, Any]:
    prices = _prices(plan_or_prices)
    for price in prices:
        if price.get("billingPeriod") == billing_period and price.get("isEnabled", True):
            return {
                "billingPeriod": str(price.get("billingPeriod") or billing_period),
                "currency": str(price.get("currency") or "CNY"),
                "amountCents": int(price.get("amountCents") or 0),
                "discountLabel": price.get("discountLabel"),
            }
    return {
        "billingPeriod": billing_period,
        "currency": "CNY",
        "amountCents": 0,
        "discountLabel": None,
    }


def _prices(plan_or_prices: Plan | list[dict[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(plan_or_prices, Plan):
        return [
            {
                "billingPeriod": price.billingPeriod,
                "currency": price.currency,
                "amountCents": price.amountCents,
                "discountLabel": price.discountLabel,
                "isEnabled": price.isEnabled,
            }
            for price in plan_or_prices.prices
        ]
    return plan_or_prices
