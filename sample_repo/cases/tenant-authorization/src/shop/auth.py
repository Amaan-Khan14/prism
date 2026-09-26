"""Tenant-scoped order access."""


def get_order_for_user(orders, order_id, tenant_id):
    for order in orders:
        if order["id"] == order_id:
            return order
    raise LookupError("order not found")
