import threading
import unittest
from http.client import HTTPConnection
from urllib.parse import urlencode

from src.server import ShortenerHTTPServer
from src.shortener import Shortener


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.server = ShortenerHTTPServer(
            ("127.0.0.1", 0),
            linear_probing_shortener=Shortener(
                strategy="linear_probing", capacity=3
            ),
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(self, method, path, body=None, headers=None):
        connection = HTTPConnection("127.0.0.1", self.port, timeout=2)
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        status = response.status
        location = response.getheader("Location")
        response_body = response.read().decode("utf-8")
        connection.close()
        return status, location, response_body

    def shorten(self, url, strategy="chaining", host=None):
        body = urlencode(
            [("url", url), ("strategy", strategy)]
        ).encode("utf-8")
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        if host is not None:
            headers["Host"] = host
        return self.request(
            "POST",
            "/shorten",
            body=body,
            headers=headers,
        )

    def test_homepage_contains_url_form(self):
        status, _, body = self.request("GET", "/")

        self.assertEqual(status, 200)
        self.assertIn('action="/shorten"', body)
        self.assertIn('name="url"', body)
        self.assertIn('name="strategy"', body)
        self.assertIn('type="submit"', body)

    def test_shortening_shows_link_that_redirects(self):
        original_url = "https://example.com/path"

        status, _, body = self.shorten(
            original_url, host="localhost:8000"
        )

        self.assertEqual(status, 200)
        self.assertIn('<a href="/0">/0</a>', body)
        self.assertNotIn("localhost", body)

        status, location, _ = self.request("GET", "/0")

        self.assertEqual(status, 302)
        self.assertEqual(location, original_url)

    def test_table_shows_chains_nodes_and_horner_steps(self):
        urls = [f"https://example.com/item-{index}" for index in range(9)]
        for url in urls:
            status, _, _ = self.shorten(url)
            self.assertEqual(status, 200)

        status, _, body = self.request("GET", "/table")

        self.assertEqual(status, 200)
        self.assertEqual(body.count('class="node"'), len(urls))
        self.assertIn("&rarr;", body)
        self.assertIn("<details>", body)
        self.assertIn("ord(", body)
        self.assertIn("최종 버킷", body)
        for url in urls:
            with self.subTest(url=url):
                self.assertIn(url, body)

    def test_linear_probing_form_redirect_and_table_view(self):
        status, _, home_body = self.request(
            "GET", "/?strategy=linear_probing"
        )
        self.assertEqual(status, 200)
        self.assertIn(
            '<option value="linear_probing" selected>', home_body
        )

        urls = (
            "https://example.com/a",
            "https://example.com/b",
            "https://example.com/c",
        )
        for url in urls:
            status, _, _ = self.shorten(
                url, strategy="linear_probing", host="localhost:8000"
            )
            self.assertEqual(status, 200)

        status, _, full_table_body = self.shorten(
            "https://example.com/full", strategy="linear_probing"
        )
        self.assertEqual(status, 507)
        self.assertIn("hash table is full", full_table_body)

        status, _, result_body = self.shorten(
            urls[0], strategy="linear_probing", host="localhost:8000"
        )
        self.assertEqual(status, 200)
        self.assertIn(
            '<a href="/0?strategy=linear_probing">/0?strategy=linear_probing</a>',
            result_body,
        )
        self.assertNotIn("localhost", result_body)

        status, location, _ = self.request(
            "GET", "/0?strategy=linear_probing"
        )
        self.assertEqual(status, 302)
        self.assertEqual(location, urls[0])

        status, _, body = self.request(
            "GET", "/table?strategy=linear_probing"
        )
        self.assertEqual(status, 200)
        self.assertIn("선형 탐지", body)
        self.assertIn("탐색 경로", body)
        self.assertIn("방문한 칸 수", body)
        self.assertIn("Horner", body)
        self.assertIn("mod 3", body)
        self.assertIn('href="/0?strategy=linear_probing"', body)
        self.assertNotIn("localhost", body)
        for url in urls:
            with self.subTest(url=url):
                self.assertIn(url, body)

    def test_unknown_strategy_is_rejected(self):
        body = urlencode(
            [("url", "https://example.com/"), ("strategy", "quadratic")]
        ).encode("utf-8")
        status, _, _ = self.request(
            "POST",
            "/shorten",
            body=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        self.assertEqual(status, 400)

    def test_invalid_urls_and_codes_return_not_found_responses(self):
        status, _, _ = self.shorten("ftp://example.com/file")
        self.assertEqual(status, 400)

        for path in ("/!", "/Z"):
            with self.subTest(path=path):
                status, _, _ = self.request("GET", path)
                self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
