import unittest

from src.hash_table import HashTable


class HashTableTests(unittest.TestCase):
    def test_empty_string_key_and_missing_key(self):
        table = HashTable()

        self.assertIsNone(table.get(""))
        self.assertEqual(len(table), 0)

        table.put("", "empty key")

        self.assertEqual(table.get(""), "empty key")
        self.assertEqual(len(table), 1)

    def test_colliding_keys_keep_their_values(self):
        table = HashTable(capacity=1)

        table.put("first key", "first")
        table.put("second key", "second")

        self.assertEqual(table.get("first key"), "first")
        self.assertEqual(table.get("second key"), "second")
        self.assertEqual(len(table), 2)

    def test_updating_a_key_does_not_increase_length(self):
        table = HashTable()
        table.put("key", "old")

        table.put("key", "new")

        self.assertEqual(table.get("key"), "new")
        self.assertEqual(len(table), 1)

    def test_single_bucket_handles_load_factor_four(self):
        table = HashTable(capacity=1, max_load=None)
        entries = [(f"key-{index}", f"value-{index}") for index in range(4)]

        for key, value in entries:
            table.put(key, value)

        self.assertEqual(table.capacity, 1)
        self.assertEqual(len(table), len(entries))
        for key, value in entries:
            with self.subTest(key=key):
                self.assertEqual(table.get(key), value)

    def test_lookup_reports_nodes_compared(self):
        table = HashTable(capacity=1, max_load=None)
        table.put("first", "first value")
        table.put("second", "second value")

        self.assertEqual(
            table.get_with_comparisons("first"), ("first value", 1)
        )
        self.assertEqual(
            table.get_with_comparisons("second"), ("second value", 2)
        )
        self.assertEqual(table.get_with_comparisons("missing"), (None, 2))


if __name__ == "__main__":
    unittest.main()
