"""Messages sent after an order state change succeeds."""


def receipt_message(order_id, total):
    return f"Order {order_id} charged ${total:.2f}"


def refund_message(order_id, total):
    return f"Order {order_id} refunded ${total:.2f}"
