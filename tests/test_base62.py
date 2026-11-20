import unittest

from src.base62 import decode, encode


class Base62Tests(unittest.TestCase):
    def test_zero_and_alphabet_boundaries(self):
        self.assertEqual(encode(0), "0")
        self.assertEqual(encode(9), "9")
        self.assertEqual(encode(10), "a")
        self.assertEqual(encode(35), "z")
        self.assertEqual(encode(36), "A")
        self.assertEqual(encode(61), "Z")
        self.assertEqual(encode(62), "10")

    def test_round_trip_large_integer(self):
        number = 10**100 + 123456789
        self.assertEqual(decode(encode(number)), number)

    def test_encode_rejects_invalid_values(self):
        for value in (-1,):
            with self.subTest(value=value), self.assertRaises(ValueError):
                encode(value)
        for value in (True, 1.5, "12"):
            with self.subTest(value=value), self.assertRaises(TypeError):
                encode(value)

    def test_decode_rejects_invalid_values(self):
        for value in ("", "a?", "hello "):
            with self.subTest(value=value), self.assertRaises(ValueError):
                decode(value)
        with self.assertRaises(TypeError):
            decode(12)


if __name__ == "__main__":
    unittest.main()
