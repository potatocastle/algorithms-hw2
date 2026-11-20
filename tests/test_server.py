import threading
import unittest
from http.client import HTTPConnection
from urllib.parse import urlencode

from src.server import ShortenerHTTPServer


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.server = ShortenerHTTPServer(("127.0.0.1", 0))
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

    def shorten(self, url):
        body = urlencode([("url", url)]).encode("utf-8")
        return self.request(
            "POST",
            "/shorten",
            body=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    def test_homepage_contains_url_form(self):
        status, _, body = self.request("GET", "/")

        self.assertEqual(status, 200)
        self.assertIn('action="/shorten"', body)
        self.assertIn('name="url"', body)
        self.assertIn('type="submit"', body)

    def test_shortening_shows_link_that_redirects(self):
        original_url = "https://example.com/path"

        status, _, body = self.shorten(original_url)

        self.assertEqual(status, 200)
        self.assertIn(f"http://127.0.0.1:{self.port}/0", body)

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

    def test_invalid_urls_and_codes_return_not_found_responses(self):
        status, _, _ = self.shorten("ftp://example.com/file")
        self.assertEqual(status, 400)

        for path in ("/!", "/Z"):
            with self.subTest(path=path):
                status, _, _ = self.request("GET", path)
                self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
