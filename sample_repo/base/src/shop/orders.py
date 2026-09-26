"""Order operations; the lists model a tiny in-memory transaction boundary."""

from shop.notifications import receipt_message, refund_message
from shop.payments import total_after_discount


def place_order(orders, notifications, order_id, subtotal, discount_rate=0):
    total = total_after_discount(subtotal, discount_rate)
    message = receipt_message(order_id, total)
    order = {"id": order_id, "total": total, "status": "paid"}
    notifications.append(message)
    orders.append(order)
    return order


def refund_order(order, notifications):
    if order["status"] != "paid":
        raise ValueError("only paid orders can be refunded")
    message = refund_message(order["id"], order["total"])
    notifications.append(message)
    order["status"] = "refunded"
    return order
