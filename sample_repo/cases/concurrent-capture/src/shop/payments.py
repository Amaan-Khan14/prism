"""Small payment rules with deliberately clear contracts."""

from decimal import Decimal, ROUND_HALF_UP


def money(value):
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def total_after_discount(subtotal, discount_rate):
    """Return a dollar amount; the rate must be between zero and one."""
    if not 0 <= discount_rate <= 1:
        raise ValueError("discount rate must be between 0 and 1")
    return money(money(subtotal) * (1 - Decimal(str(discount_rate))))


def settle_payout(balance, amount, daily_cap, expedited=False):
    """Return the remaining balance after a payout within the daily cap."""
    requested = money(amount)
    if requested <= 0 or requested > money(daily_cap):
        raise ValueError("payout is outside the daily limit")
    if requested > money(balance):
        raise ValueError("insufficient balance")
    return money(balance) - requested


def capture_payment(captures, idempotency_key, amount, lock):
    """Capture once per key, including when concurrent callers race."""
    if idempotency_key in captures:
        return captures[idempotency_key]
    with lock:
        receipt = {"key": idempotency_key, "amount": money(amount)}
        captures[idempotency_key] = receipt
        return receipt
