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
        table = HashTable(capacity=1)
        entries = [(f"key-{index}", f"value-{index}") for index in range(4)]

        for key, value in entries:
            table.put(key, value)

        self.assertEqual(len(table), len(entries))
        for key, value in entries:
            with self.subTest(key=key):
                self.assertEqual(table.get(key), value)


if __name__ == "__main__":
    unittest.main()
