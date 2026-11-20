import unittest

from src.shortener import Shortener


class ShortenerTests(unittest.TestCase):
    def test_distinct_urls_receive_distinct_round_trip_codes(self):
        shortener = Shortener()
        urls = (
            "https://example.com/first",
            "http://example.org/second",
        )

        codes = [shortener.shorten(url) for url in urls]

        self.assertEqual(codes, ["0", "1"])
        self.assertNotEqual(codes[0], codes[1])
        for code, url in zip(codes, urls):
            with self.subTest(code=code):
                self.assertEqual(shortener.expand(code), url)

    def test_same_url_reuses_its_code(self):
        shortener = Shortener()
        url = "https://example.com/repeated"

        first_code = shortener.shorten(url)
        second_code = shortener.shorten(url)

        self.assertEqual(first_code, second_code)
        self.assertEqual(shortener.expand(first_code), url)

    def test_rejects_invalid_urls(self):
        shortener = Shortener()
        invalid_urls = (
            "",
            "ftp://example.com/file",
            "https:///missing-host",
            "example.com/path",
            " https://example.com/path",
        )

        for url in invalid_urls:
            with self.subTest(url=url), self.assertRaises(ValueError):
                shortener.shorten(url)

        for url in (None, 42):
            with self.subTest(url=url), self.assertRaises(TypeError):
                shortener.shorten(url)

    def test_distinguishes_invalid_and_unknown_codes(self):
        shortener = Shortener()

        for code in ("", "!", "bad-code"):
            with self.subTest(code=code), self.assertRaises(ValueError):
                shortener.expand(code)

        with self.assertRaises(KeyError):
            shortener.expand("Z")

        with self.assertRaises(TypeError):
            shortener.expand(None)


if __name__ == "__main__":
    unittest.main()
