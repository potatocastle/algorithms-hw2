"""HTTP interface for the in-memory URL shortener."""

from __future__ import annotations

import argparse
from html import escape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qsl, urlsplit

from src.shortener import Shortener

MAX_FORM_BYTES = 64 * 1024


class ShortenerRequestHandler(BaseHTTPRequestHandler):
    def _app_server(self) -> ShortenerHTTPServer:
        if not isinstance(self.server, ShortenerHTTPServer):
            raise RuntimeError("request handler requires ShortenerHTTPServer")
        return self.server

    def _send_html(self, status: HTTPStatus, body: str) -> None:
        encoded_body = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded_body)))
        self.end_headers()
        self.wfile.write(encoded_body)

    def _send_error_page(self, status: HTTPStatus, message: str) -> None:
        body = (
            "<!doctype html><html lang=\"ko\"><meta charset=\"utf-8\">"
            f"<title>{status.value} {escape(status.phrase)}</title>"
            f"<main><h1>{status.value} {escape(status.phrase)}</h1>"
            f"<p>{escape(message)}</p><a href=\"/\">처음으로</a></main></html>"
        )
        self._send_html(status, body)

    def _request_origin(self) -> str:
        host = self.headers.get("Host", "")
        if not host or any(
            character.isspace() or character in "/\\?#@"
            for character in host
        ):
            address = self._app_server().server_address
            fallback_host = address[0]
            if fallback_host in ("", "0.0.0.0"):
                fallback_host = "localhost"
            if ":" in fallback_host and not fallback_host.startswith("["):
                fallback_host = f"[{fallback_host}]"
            host = f"{fallback_host}:{address[1]}"

        scheme = self.headers.get("X-Forwarded-Proto", "http")
        scheme = scheme.split(",", 1)[0].strip().lower()
        if scheme not in ("http", "https"):
            scheme = "http"
        return f"{scheme}://{host}"

    def _home_page(self) -> str:
        return (
            "<!doctype html><html lang=\"ko\"><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            "<title>URL 단축기</title><main>"
            "<h1>URL 단축기</h1>"
            "<form method=\"post\" action=\"/shorten\">"
            "<label for=\"url\">줄일 URL</label> "
            "<input id=\"url\" name=\"url\" type=\"url\" required "
            "placeholder=\"https://example.com\">"
            "<button type=\"submit\">줄이기</button></form>"
            "<p><a href=\"/table\">해시 테이블 보기</a></p>"
            "</main></html>"
        )

    def _table_page(self) -> str:
        table = self._app_server().shortener.url_table
        origin = escape(self._request_origin(), quote=True)
        buckets = []

        for bucket_index, entries in table.iter_buckets():
            nodes = []
            for node_index, (url, value) in enumerate(entries):
                if not isinstance(value, str):
                    raise RuntimeError("URL table values must be short codes")
                code = value
                short_link = f"{origin}/{escape(code, quote=True)}"
                steps = table.hash_steps(url)
                step_items = []
                for step_number, (character, before, code_point, after) in enumerate(
                    steps, start=1
                ):
                    step_items.append(
                        "<li>"
                        f"{step_number}: (31 × {before} + "
                        f"ord({escape(repr(character))}) [{code_point}]) "
                        f"mod {table.capacity} = {after}"
                        "</li>"
                    )
                if not step_items:
                    step_items.append("<li>빈 문자열: 초기값 0, 인덱스 0</li>")
                step_items.append(
                    f"<li>최종 버킷 인덱스: {bucket_index}</li>"
                )
                node = (
                    '<article class="node">'
                    f"<p><strong>URL 키</strong><br><code>{escape(url)}</code></p>"
                    f"<p><strong>짧은 코드</strong><br><code>{escape(code)}</code></p>"
                    f"<p><strong>짧은 링크</strong><br>"
                    f'<a href="{short_link}">{short_link}</a></p>'
                    "<details><summary>호너 해시 계산 과정</summary>"
                    f"<ol>{''.join(step_items)}</ol></details>"
                    "</article>"
                )
                if node_index:
                    nodes.append('<span class="arrow" aria-hidden="true">&rarr;</span>')
                nodes.append(node)

            contents = "".join(nodes) if nodes else '<p class="empty">비어 있음</p>'
            buckets.append(
                f'<section class="bucket"><h2>칸 {bucket_index}</h2>'
                f'<div class="chain">{contents}</div></section>'
            )

        return (
            "<!doctype html><html lang=\"ko\"><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            "<title>해시 테이블</title>"
            "<style>"
            "body{font-family:sans-serif;margin:1.5rem}"
            ".bucket{border:1px solid #bbb;padding:.75rem;margin:.75rem 0}"
            ".chain{display:flex;align-items:flex-start;gap:.5rem;flex-wrap:wrap}"
            ".node{border:1px solid #789;padding:.75rem;max-width:38rem}"
            ".node code{overflow-wrap:anywhere}.arrow{font-size:1.5rem;padding-top:2rem}"
            ".empty{color:#666}"
            "</style><main><h1>URL 해시 테이블</h1>"
            f"<p>칸 수: {table.capacity} · 저장된 URL: {len(table)}</p>"
            f"{''.join(buckets)}<p><a href=\"/\">URL 줄이기</a></p>"
            "</main></html>"
        )

    def do_GET(self) -> None:
        try:
            path = urlsplit(self.path).path
        except ValueError:
            self._send_error_page(HTTPStatus.NOT_FOUND, "잘못된 경로입니다.")
            return

        if path == "/":
            self._send_html(HTTPStatus.OK, self._home_page())
            return
        if path == "/table":
            self._send_html(HTTPStatus.OK, self._table_page())
            return
        if not path.startswith("/") or "/" in path[1:] or not path[1:]:
            self._send_error_page(HTTPStatus.NOT_FOUND, "페이지를 찾을 수 없습니다.")
            return

        code = path[1:]
        try:
            url = self._app_server().shortener.expand(code)
        except (KeyError, ValueError):
            self._send_error_page(HTTPStatus.NOT_FOUND, "짧은 링크를 찾을 수 없습니다.")
            return
        self.send_response(HTTPStatus.FOUND)
        self.send_header("Location", url)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self) -> None:
        try:
            path = urlsplit(self.path).path
        except ValueError:
            self._send_error_page(HTTPStatus.BAD_REQUEST, "잘못된 요청 경로입니다.")
            return
        if path != "/shorten":
            self._send_error_page(HTTPStatus.NOT_FOUND, "페이지를 찾을 수 없습니다.")
            return

        content_type = self.headers.get("Content-Type", "")
        if content_type.split(";", 1)[0].strip().lower() != (
            "application/x-www-form-urlencoded"
        ):
            self._send_error_page(
                HTTPStatus.BAD_REQUEST, "URL 폼 형식으로 요청해 주세요."
            )
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_error_page(HTTPStatus.BAD_REQUEST, "잘못된 폼 데이터입니다.")
            return
        if content_length <= 0:
            self._send_error_page(HTTPStatus.BAD_REQUEST, "URL을 입력해 주세요.")
            return
        if content_length > MAX_FORM_BYTES:
            self._send_error_page(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "폼 데이터가 너무 큽니다."
            )
            return

        form_body = self.rfile.read(content_length)
        if len(form_body) != content_length:
            self._send_error_page(HTTPStatus.BAD_REQUEST, "폼 데이터가 잘렸습니다.")
            return
        try:
            fields = parse_qsl(form_body.decode("utf-8"), keep_blank_values=True)
        except UnicodeDecodeError:
            self._send_error_page(HTTPStatus.BAD_REQUEST, "폼은 UTF-8이어야 합니다.")
            return

        urls = [value for name, value in fields if name == "url"]
        if len(urls) != 1:
            self._send_error_page(
                HTTPStatus.BAD_REQUEST, "URL 필드를 하나 입력해 주세요."
            )
            return

        try:
            code = self._app_server().shortener.shorten(urls[0])
        except ValueError as error:
            self._send_error_page(HTTPStatus.BAD_REQUEST, str(error))
            return

        short_link = f"{self._request_origin()}/{code}"
        escaped_link = escape(short_link, quote=True)
        body = (
            "<!doctype html><html lang=\"ko\"><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            "<title>짧은 링크</title><main><h1>짧은 링크</h1>"
            f'<p><a href="{escaped_link}">{escaped_link}</a></p>'
            f"<p>코드: <code>{escape(code)}</code></p>"
            '<p><a href="/">다른 URL 줄이기</a> · '
            '<a href="/table">해시 테이블 보기</a></p></main></html>'
        )
        self._send_html(HTTPStatus.OK, body)


class ShortenerHTTPServer(HTTPServer):
    allow_reuse_address = True

    def __init__(
        self,
        server_address: tuple[str, int],
        shortener: Shortener | None = None,
    ) -> None:
        self.shortener = shortener if shortener is not None else Shortener()
        super().__init__(server_address, ShortenerRequestHandler)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the URL shortener server.")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    server = ShortenerHTTPServer(("0.0.0.0", args.port))
    print(f"URL shortener listening on port {args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping URL shortener.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
