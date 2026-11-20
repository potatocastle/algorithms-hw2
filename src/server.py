"""HTTP interface for the in-memory URL shortener."""

from __future__ import annotations

import argparse
from html import escape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qsl, urlsplit

from src.hash_table import HashTable, LinearProbingHashTable
from src.shortener import Shortener

MAX_FORM_BYTES = 64 * 1024


class ShortenerRequestHandler(BaseHTTPRequestHandler):
    def _app_server(self) -> ShortenerHTTPServer:
        if not isinstance(self.server, ShortenerHTTPServer):
            raise RuntimeError("request handler requires ShortenerHTTPServer")
        return self.server

    @staticmethod
    def _query_strategy(query: str) -> str:
        strategies = [
            value
            for name, value in parse_qsl(query, keep_blank_values=True)
            if name == "strategy"
        ]
        if not strategies:
            return "chaining"
        if len(strategies) != 1 or strategies[0] not in (
            "chaining",
            "linear_probing",
        ):
            raise ValueError("unknown hash-table strategy")
        return strategies[0]

    @staticmethod
    def _strategy_query(strategy: str) -> str:
        return "" if strategy == "chaining" else "?strategy=linear_probing"

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

    def _home_page(self, strategy: str) -> str:
        chaining_selected = " selected" if strategy == "chaining" else ""
        linear_selected = (
            " selected" if strategy == "linear_probing" else ""
        )
        table_href = f"/table{self._strategy_query(strategy)}"
        return (
            "<!doctype html><html lang=\"ko\"><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            "<title>URL 단축기</title><main>"
            "<h1>URL 단축기</h1>"
            "<form method=\"post\" action=\"/shorten\">"
            "<label for=\"url\">줄일 URL</label> "
            "<input id=\"url\" name=\"url\" type=\"url\" required "
            "placeholder=\"https://example.com\">"
            '<label for="strategy">충돌 처리</label> '
            '<select id="strategy" name="strategy">'
            f'<option value="chaining"{chaining_selected}>개별 체이닝</option>'
            f'<option value="linear_probing"{linear_selected}>선형 탐지</option>'
            "</select> "
            "<button type=\"submit\">줄이기</button></form>"
            f'<p><a href="{table_href}">선택한 해시 테이블 보기</a></p>'
            "</main></html>"
        )

    def _table_page(self, strategy: str) -> str:
        shortener = self._app_server().shortener_for(strategy)
        table = shortener.url_table
        if strategy == "linear_probing":
            return self._linear_probing_table_page(table)

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
            "<title>개별 체이닝 해시 테이블</title>"
            "<style>"
            "body{font-family:sans-serif;margin:1.5rem}"
            ".bucket{border:1px solid #bbb;padding:.75rem;margin:.75rem 0}"
            ".chain{display:flex;align-items:flex-start;gap:.5rem;flex-wrap:wrap}"
            ".node{border:1px solid #789;padding:.75rem;max-width:38rem}"
            ".node code{overflow-wrap:anywhere}.arrow{font-size:1.5rem;padding-top:2rem}"
            ".empty{color:#666}"
            "</style><main><h1>개별 체이닝 해시 테이블</h1>"
            f"<p>칸 수: {table.capacity} · 저장된 URL: {len(table)}</p>"
            f"{''.join(buckets)}"
            '<p><a href="/table?strategy=linear_probing">선형 탐지 보기</a> · '
            '<a href="/">URL 줄이기</a></p>'
            "</main></html>"
        )

    def _linear_probing_table_page(
        self, table: HashTable | LinearProbingHashTable
    ) -> str:
        origin = escape(self._request_origin(), quote=True)
        slots = []
        for slot_index, entries in table.iter_buckets():
            if not entries:
                slots.append(
                    f'<section class="slot empty"><h2>칸 {slot_index}</h2>'
                    "<p>비어 있음</p></section>"
                )
                continue

            url, value = entries[0]
            if not isinstance(value, str):
                raise RuntimeError("URL table values must be short codes")
            code = value
            short_link = (
                f"{origin}/{escape(code, quote=True)}"
                "?strategy=linear_probing"
            )
            steps = table.hash_steps(url)
            home_index = steps[-1][3] if steps else 0
            _, probe_count = table.get_with_comparisons(url)
            probe_path = ", ".join(
                str((home_index + offset) % table.capacity)
                for offset in range(probe_count)
            )
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
                step_items.append("<li>빈 문자열: 초기값 0, 홈 칸 0</li>")
            step_items.extend(
                (
                    f"<li>홈 칸: {home_index}</li>",
                    f"<li>탐색 경로: {escape(probe_path)}</li>",
                    f"<li>방문한 칸 수: {probe_count}</li>",
                    f"<li>저장 칸: {slot_index}</li>",
                )
            )
            slots.append(
                f'<section class="slot"><h2>칸 {slot_index}</h2>'
                f"<p><strong>URL 키</strong><br><code>{escape(url)}</code></p>"
                f"<p><strong>짧은 코드</strong><br><code>{escape(code)}</code></p>"
                "<p><strong>짧은 링크</strong><br>"
                f'<a href="{short_link}">{short_link}</a></p>'
                "<details><summary>Horner 계산과 선형 탐지 과정</summary>"
                f"<ol>{''.join(step_items)}</ol></details></section>"
            )

        return (
            "<!doctype html><html lang=\"ko\"><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            "<title>선형 탐지 해시 테이블</title>"
            "<style>"
            "body{font-family:sans-serif;margin:1.5rem}"
            ".slots{display:grid;grid-template-columns:repeat(auto-fit,minmax(15rem,1fr));gap:.75rem}"
            ".slot{border:1px solid #789;padding:.75rem;overflow-wrap:anywhere}"
            ".empty{color:#666;border-color:#bbb}"
            "</style><main><h1>선형 탐지 해시 테이블</h1>"
            f"<p>칸 수: {table.capacity} · 저장된 URL: {len(table)}</p>"
            f'<div class="slots">{"".join(slots)}</div>'
            '<p><a href="/table?strategy=chaining">개별 체이닝 보기</a> · '
            '<a href="/">URL 줄이기</a></p>'
            "</main></html>"
        )

    def do_GET(self) -> None:
        try:
            parsed_path = urlsplit(self.path)
            path = parsed_path.path
        except ValueError:
            self._send_error_page(HTTPStatus.NOT_FOUND, "잘못된 경로입니다.")
            return

        if path == "/":
            try:
                strategy = self._query_strategy(parsed_path.query)
            except ValueError as error:
                self._send_error_page(HTTPStatus.BAD_REQUEST, str(error))
                return
            self._send_html(HTTPStatus.OK, self._home_page(strategy))
            return
        if path == "/table":
            try:
                strategy = self._query_strategy(parsed_path.query)
            except ValueError as error:
                self._send_error_page(HTTPStatus.BAD_REQUEST, str(error))
                return
            self._send_html(HTTPStatus.OK, self._table_page(strategy))
            return
        if not path.startswith("/") or "/" in path[1:] or not path[1:]:
            self._send_error_page(HTTPStatus.NOT_FOUND, "페이지를 찾을 수 없습니다.")
            return

        code = path[1:]
        try:
            strategy = self._query_strategy(parsed_path.query)
            url = self._app_server().shortener_for(strategy).expand(code)
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
        strategies = [value for name, value in fields if name == "strategy"]
        if len(urls) != 1 or len(strategies) > 1:
            self._send_error_page(
                HTTPStatus.BAD_REQUEST, "URL과 충돌 처리 방식을 확인해 주세요."
            )
            return
        strategy = strategies[0] if strategies else "chaining"
        if strategy not in ("chaining", "linear_probing"):
            self._send_error_page(
                HTTPStatus.BAD_REQUEST, "알 수 없는 충돌 처리 방식입니다."
            )
            return

        try:
            code = self._app_server().shortener_for(strategy).shorten(urls[0])
        except ValueError as error:
            self._send_error_page(HTTPStatus.BAD_REQUEST, str(error))
            return
        except OverflowError as error:
            self._send_error_page(HTTPStatus.INSUFFICIENT_STORAGE, str(error))
            return

        short_link = (
            f"{self._request_origin()}/{code}"
            f"{self._strategy_query(strategy)}"
        )
        escaped_link = escape(short_link, quote=True)
        body = (
            "<!doctype html><html lang=\"ko\"><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            "<title>짧은 링크</title><main><h1>짧은 링크</h1>"
            f'<p><a href="{escaped_link}">{escaped_link}</a></p>'
            f"<p>코드: <code>{escape(code)}</code></p>"
            f'<p><a href="/?strategy={escape(strategy)}">다른 URL 줄이기</a> · '
            f'<a href="/table{self._strategy_query(strategy)}">'
            "해시 테이블 보기</a></p></main></html>"
        )
        self._send_html(HTTPStatus.OK, body)


class ShortenerHTTPServer(HTTPServer):
    allow_reuse_address = True

    def __init__(
        self,
        server_address: tuple[str, int],
        shortener: Shortener | None = None,
        linear_probing_shortener: Shortener | None = None,
    ) -> None:
        self.shortener = shortener if shortener is not None else Shortener()
        if self.shortener.strategy != "chaining":
            raise ValueError("shortener must use chaining strategy")
        self.linear_probing_shortener = (
            linear_probing_shortener
            if linear_probing_shortener is not None
            else Shortener(strategy="linear_probing")
        )
        if self.linear_probing_shortener.strategy != "linear_probing":
            raise ValueError(
                "linear_probing_shortener must use linear_probing strategy"
            )
        super().__init__(server_address, ShortenerRequestHandler)

    def shortener_for(self, strategy: str) -> Shortener:
        if strategy == "chaining":
            return self.shortener
        if strategy == "linear_probing":
            return self.linear_probing_shortener
        raise ValueError("unknown hash-table strategy")


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
