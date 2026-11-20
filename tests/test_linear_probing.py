import unittest

from src.hash_table import LinearProbingHashTable


class LinearProbingHashTableTests(unittest.TestCase):
    def test_collisions_wrap_from_last_slot_to_first(self):
        table = LinearProbingHashTable(capacity=3)

        table.put("b", "first")
        table.put("e", "second")

        self.assertEqual(table.get("b"), "first")
        self.assertEqual(table.get_with_comparisons("e"), ("second", 2))
        buckets = list(table.iter_buckets())
        self.assertEqual(buckets[0], (0, (("e", "second"),)))
        self.assertEqual(buckets[2], (2, (("b", "first"),)))

    def test_full_table_fails_cleanly_and_still_allows_updates(self):
        table = LinearProbingHashTable(capacity=2)
        table.put("a", "old")
        table.put("b", "second")

        self.assertEqual(table.get_with_comparisons("missing"), (None, 2))
        with self.assertRaises(OverflowError):
            table.put("c", "third")

        table.put("a", "new")
        self.assertEqual(table.get("a"), "new")
        self.assertEqual(len(table), 2)

    def test_empty_key_update_and_missing_key(self):
        table = LinearProbingHashTable()

        self.assertIsNone(table.get(""))
        table.put("", "old")
        table.put("", "new")

        self.assertEqual(table.get(""), "new")
        self.assertEqual(table.get("absent"), None)
        self.assertEqual(len(table), 1)

    def test_invalid_key_type_is_rejected(self):
        table = LinearProbingHashTable()

        with self.assertRaises(TypeError):
            table.put(1, "value")
        with self.assertRaises(TypeError):
            table.get(None)


if __name__ == "__main__":
    unittest.main()
