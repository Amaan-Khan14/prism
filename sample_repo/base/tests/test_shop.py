import threading
import unittest
from decimal import Decimal

from shop.auth import get_order_for_user
from shop.orders import place_order, refund_order
from shop.payments import capture_payment, settle_payout, total_after_discount


class ShopTests(unittest.TestCase):
    def test_discount(self):
        self.assertEqual(total_after_discount(100, 0.1), Decimal("90.00"))

    def test_order_and_receipt(self):
        orders, messages = [], []
        order = place_order(orders, messages, "o-1", 20, 0.1)
        self.assertEqual(order["total"], Decimal("18.00"))
        self.assertEqual(len(messages), 1)

    def test_refund(self):
        order = {"id": "o-1", "total": Decimal("18.00"), "status": "paid"}
        messages = []
        refund_order(order, messages)
        self.assertEqual(order["status"], "refunded")
        self.assertEqual(len(messages), 1)

    def test_payout(self):
        self.assertEqual(settle_payout(100, 20, 50), Decimal("80.00"))

    def test_capture(self):
        captures, lock = {}, threading.Lock()
        first = capture_payment(captures, "k1", 20, lock)
        self.assertIs(first, capture_payment(captures, "k1", 20, lock))
        self.assertEqual(len(captures), 1)

    def test_tenant_access(self):
        orders = [{"id": "o-1", "tenant_id": "tenant-a"}]
        self.assertEqual(get_order_for_user(orders, "o-1", "tenant-a"), orders[0])


if __name__ == "__main__":
    unittest.main()
