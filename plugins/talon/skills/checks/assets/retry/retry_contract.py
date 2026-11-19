"""Exercise order retries using a project-local retry_fixture adapter."""

import tempfile
import unittest
from pathlib import Path

from retry_fixture import create_store, read_orders, submit_order


class LostAcknowledgement(TimeoutError):
    """The caller did not receive the order confirmation."""


class OrderRetryTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.store = Path(directory.name) / "orders.sqlite3"
        create_store(self.store)

    def test_retry_after_lost_acknowledgement_keeps_one_order(self):
        operation_key = "order-1"
        item = "notebook"

        def lose_acknowledgement(_order_id):
            raise LostAcknowledgement("simulated loss after the order was committed")

        with self.assertRaises(LostAcknowledgement):
            submit_order(self.store, operation_key, item, acknowledge=lose_acknowledgement)

        original_rows = read_orders(self.store)
        self.assertEqual(len(original_rows), 1)
        order_id, saved_key, saved_item = original_rows[0]
        self.assertEqual((saved_key, saved_item), (operation_key, item))

        retry_id = submit_order(self.store, operation_key, item)

        self.assertEqual(read_orders(self.store), original_rows)
        self.assertEqual(retry_id, order_id)

    def test_distinct_operation_keys_create_distinct_orders(self):
        item = "notebook"
        first_id = submit_order(self.store, "order-1", item)
        second_id = submit_order(self.store, "order-2", item)

        self.assertNotEqual(first_id, second_id)
        self.assertCountEqual(
            read_orders(self.store),
            [(first_id, "order-1", item), (second_id, "order-2", item)],
        )


if __name__ == "__main__":
    unittest.main()
