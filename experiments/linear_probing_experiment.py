"""Compare separate chaining and linear probing on the same URL keys."""

import csv
import math
import random
from pathlib import Path
from typing import NamedTuple
from xml.sax.saxutils import escape

from src.hash_table import HashTable, LinearProbingHashTable

CAPACITY = 4093
RANDOM_SEED = 2026
LOAD_FACTORS = tuple(step / 10 for step in range(1, 10))
OUTPUT_DIR = Path(__file__).resolve().parent
CSV_PATH = OUTPUT_DIR / "linear_probing_results.csv"
SVG_PATH = OUTPUT_DIR / "linear_probing_results.svg"
PDF_PATH = OUTPUT_DIR / "linear_probing_report.pdf"


class ComparisonResult(NamedTuple):
    target_alpha: float
    actual_alpha: float
    item_count: int
    chaining_success_measured: float
    chaining_success_theory: float
    chaining_failed_measured: float
    chaining_failed_theory: float
    linear_success_measured: float
    linear_success_theory: float
    linear_failed_measured: float
    linear_failed_theory: float


def random_url(rng: random.Random, label: str, index: int) -> str:
    token = rng.getrandbits(64)
    return f"https://{label}-{token:016x}.example/{index}"


def measure() -> list[ComparisonResult]:
    rng = random.Random(RANDOM_SEED)
    results = []

    for target_alpha in LOAD_FACTORS:
        item_count = int(target_alpha * CAPACITY + 0.5)
        actual_alpha = item_count / CAPACITY
        urls = [
            random_url(rng, "item", index)
            for index in range(item_count)
        ]
        missing_urls = [
            random_url(rng, "missing", index)
            for index in range(item_count)
        ]
        chaining = HashTable(capacity=CAPACITY, max_load=None)
        linear = LinearProbingHashTable(capacity=CAPACITY, max_load=None)

        for index, url in enumerate(urls):
            chaining.put(url, str(index))
            linear.put(url, str(index))

        chaining_success = 0
        linear_success = 0
        for index, url in enumerate(urls):
            chain_value, chain_probes = chaining.get_with_comparisons(url)
            linear_value, linear_probes = linear.get_with_comparisons(url)
            expected_value = str(index)
            if chain_value != expected_value or linear_value != expected_value:
                raise RuntimeError(f"successful lookup failed for {url!r}")
            chaining_success += chain_probes
            linear_success += linear_probes

        chaining_failed = 0
        linear_failed = 0
        for url in missing_urls:
            chain_value, chain_probes = chaining.get_with_comparisons(url)
            linear_value, linear_probes = linear.get_with_comparisons(url)
            if chain_value is not None or linear_value is not None:
                raise RuntimeError(f"failed lookup unexpectedly found {url!r}")
            chaining_failed += chain_probes
            linear_failed += linear_probes

        results.append(
            ComparisonResult(
                target_alpha=target_alpha,
                actual_alpha=actual_alpha,
                item_count=item_count,
                chaining_success_measured=chaining_success / item_count,
                chaining_success_theory=1 + actual_alpha / 2,
                chaining_failed_measured=chaining_failed / item_count,
                chaining_failed_theory=actual_alpha,
                linear_success_measured=linear_success / item_count,
                linear_success_theory=0.5
                * (1 + 1 / (1 - actual_alpha)),
                linear_failed_measured=linear_failed / item_count,
                linear_failed_theory=0.5
                * (1 + 1 / (1 - actual_alpha) ** 2),
            )
        )

    return results


def write_csv(results: list[ComparisonResult]) -> None:
    with CSV_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(
            (
                "target_alpha",
                "actual_alpha",
                "capacity",
                "item_count",
                "chaining_success_measured",
                "chaining_success_theory",
                "chaining_failed_measured",
                "chaining_failed_theory",
                "linear_success_measured",
                "linear_success_theory",
                "linear_failed_measured",
                "linear_failed_theory",
            )
        )
        for result in results:
            writer.writerow(
                (
                    f"{result.target_alpha:.2f}",
                    f"{result.actual_alpha:.6f}",
                    CAPACITY,
                    result.item_count,
                    f"{result.chaining_success_measured:.6f}",
                    f"{result.chaining_success_theory:.6f}",
                    f"{result.chaining_failed_measured:.6f}",
                    f"{result.chaining_failed_theory:.6f}",
                    f"{result.linear_success_measured:.6f}",
                    f"{result.linear_success_theory:.6f}",
                    f"{result.linear_failed_measured:.6f}",
                    f"{result.linear_failed_theory:.6f}",
                )
            )


def _chart_series(successful: bool) -> tuple[tuple[str, str, str, str], ...]:
    suffix = "success" if successful else "failed"
    return (
        (
            "Chaining measured",
            f"chaining_{suffix}_measured",
            "#1769aa",
            "",
        ),
        (
            "Chaining theory",
            f"chaining_{suffix}_theory",
            "#1769aa",
            "8 5",
        ),
        (
            "Linear probing measured",
            f"linear_{suffix}_measured",
            "#d1495b",
            "",
        ),
        (
            "Linear probing theory",
            f"linear_{suffix}_theory",
            "#d1495b",
            "8 5",
        ),
    )


def write_svg(results: list[ComparisonResult]) -> None:
    width, height = 1200, 760
    left, plot_width = 92, 780
    plot_height, x_min, x_max = 230, 0.1, 0.9
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<title>Separate chaining and linear probing lookup costs</title>",
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="600" y="32" text-anchor="middle" font-family="sans-serif" font-size="21">Hash-table lookup cost: measured and theoretical</text>',
    ]

    for chart_index, successful in enumerate((True, False)):
        chart_top = 74 + chart_index * 340
        top = chart_top + 20
        series = _chart_series(successful)
        values = [
            getattr(result, attribute)
            for result in results
            for _, attribute, _, _ in series
        ]
        y_max = max(1.0, math.ceil(max(values) * 1.08))

        def x_position(alpha: float) -> float:
            return left + (alpha - x_min) / (x_max - x_min) * plot_width

        def y_position(value: float) -> float:
            return top + (y_max - value) / y_max * plot_height

        title = "Successful search" if successful else "Unsuccessful search"
        parts.append(
            f'<text x="{left}" y="{chart_top}" font-family="sans-serif" font-size="17">{title}</text>'
        )
        for tick in range(5):
            value = y_max * tick / 4
            y = y_position(value)
            parts.extend(
                (
                    f'<line x1="{left}" y1="{y:.2f}" x2="{left + plot_width}" y2="{y:.2f}" stroke="#ddd"/>',
                    f'<text x="{left - 10}" y="{y + 4:.2f}" text-anchor="end" font-family="sans-serif" font-size="12">{value:.1f}</text>',
                )
            )
        for result in results:
            x = x_position(result.actual_alpha)
            parts.extend(
                (
                    f'<line x1="{x:.2f}" y1="{top + plot_height}" x2="{x:.2f}" y2="{top + plot_height + 5}" stroke="#333"/>',
                    f'<text x="{x:.2f}" y="{top + plot_height + 20}" text-anchor="middle" font-family="sans-serif" font-size="11">{result.target_alpha:.1f}</text>',
                )
            )
        parts.extend(
            (
                f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" stroke="#333"/>',
                f'<line x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top + plot_height}" stroke="#333"/>',
                f'<text x="{left + plot_width / 2:.2f}" y="{top + plot_height + 42}" text-anchor="middle" font-family="sans-serif" font-size="13">Load factor alpha</text>',
                f'<text x="23" y="{top + plot_height / 2:.2f}" transform="rotate(-90 23 {top + plot_height / 2:.2f})" text-anchor="middle" font-family="sans-serif" font-size="13">Average probes</text>',
            )
        )

        for label, attribute, color, dash in series:
            points = " ".join(
                f"{x_position(result.actual_alpha):.2f},{y_position(getattr(result, attribute)):.2f}"
                for result in results
            )
            dash_attribute = (
                f' stroke-dasharray="{dash}"' if dash else ""
            )
            parts.append(
                f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2.5"{dash_attribute}/>'
            )
            for result in results:
                x = x_position(result.actual_alpha)
                y = y_position(getattr(result, attribute))
                parts.append(
                    f'<circle cx="{x:.2f}" cy="{y:.2f}" r="3" fill="{color}"/>'
                )

        legend_x = left + plot_width + 28
        for index, (label, _, color, dash) in enumerate(series):
            y = top + 36 + index * 30
            dash_attribute = (
                f' stroke-dasharray="{dash}"' if dash else ""
            )
            parts.extend(
                (
                    f'<line x1="{legend_x}" y1="{y}" x2="{legend_x + 32}" y2="{y}" stroke="{color}" stroke-width="2.5"{dash_attribute}/>',
                    f'<text x="{legend_x + 42}" y="{y + 4}" font-family="sans-serif" font-size="12">{escape(label)}</text>',
                )
            )

    parts.append("</svg>")
    SVG_PATH.write_text("\n".join(parts) + "\n", encoding="utf-8")


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _pdf_text(
    commands: list[str], x: float, y: float, size: float, text: str
) -> None:
    commands.append(
        f"BT /F1 {size:.2f} Tf {x:.2f} {y:.2f} Td ({_pdf_escape(text)}) Tj ET"
    )


def _pdf_line(
    commands: list[str],
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    color: tuple[float, float, float] = (0.25, 0.25, 0.25),
) -> None:
    red, green, blue = color
    commands.append(
        f"{red:.3f} {green:.3f} {blue:.3f} RG "
        f"{x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S"
    )


def _pdf_chart(
    commands: list[str],
    results: list[ComparisonResult],
    *,
    x: float,
    y: float,
    successful: bool,
) -> None:
    title = "Successful search probes" if successful else "Unsuccessful search probes"
    series = _chart_series(successful)
    values = [
        getattr(result, attribute)
        for result in results
        for _, attribute, _, _ in series
    ]
    y_max = max(1.0, math.ceil(max(values) * 1.08))
    plot_x, plot_y = x + 44, y + 34
    plot_width, plot_height = 355, 210
    x_min, x_max = 0.1, 0.9

    def x_position(alpha: float) -> float:
        return plot_x + (alpha - x_min) / (x_max - x_min) * plot_width

    def y_position(value: float) -> float:
        return plot_y + value / y_max * plot_height

    _pdf_text(commands, x, y + 267, 12, title)
    for tick in range(5):
        value = y_max * tick / 4
        tick_y = y_position(value)
        _pdf_line(commands, plot_x, tick_y, plot_x + plot_width, tick_y, (0.85, 0.85, 0.85))
        _pdf_text(commands, x + 4, tick_y - 3, 7, f"{value:.1f}")
    _pdf_line(commands, plot_x, plot_y, plot_x, plot_y + plot_height)
    _pdf_line(commands, plot_x, plot_y, plot_x + plot_width, plot_y)

    for result in results:
        tick_x = x_position(result.actual_alpha)
        _pdf_line(commands, tick_x, plot_y - 2, tick_x, plot_y + 2)
        _pdf_text(commands, tick_x - 8, plot_y - 13, 6, f"{result.target_alpha:.1f}")

    colors = {
        "#1769aa": (0.09, 0.41, 0.67),
        "#d1495b": (0.82, 0.29, 0.36),
    }
    for _, attribute, hex_color, dash in series:
        color = colors[hex_color]
        commands.append(
            f"{color[0]:.3f} {color[1]:.3f} {color[2]:.3f} RG"
        )
        commands.append("[4 3] 0 d" if dash else "[] 0 d")
        first = True
        for result in results:
            point_x = x_position(result.actual_alpha)
            point_y = y_position(getattr(result, attribute))
            commands.append(
                f"{point_x:.2f} {point_y:.2f} "
                f"{'m' if first else 'l'}"
            )
            first = False
        commands.append("S")
    commands.append("[] 0 d")

    legend_x, legend_y = plot_x + plot_width + 14, plot_y + plot_height - 18
    for index, (label, _, hex_color, dash) in enumerate(series):
        color = colors[hex_color]
        line_y = legend_y - index * 20
        commands.append(
            f"{color[0]:.3f} {color[1]:.3f} {color[2]:.3f} RG"
        )
        commands.append("[4 3] 0 d" if dash else "[] 0 d")
        commands.append(
            f"{legend_x:.2f} {line_y:.2f} m {legend_x + 22:.2f} {line_y:.2f} l S"
        )
        commands.append("[] 0 d")
        _pdf_text(commands, legend_x + 27, line_y - 3, 7, label)


def write_report_pdf(results: list[ComparisonResult]) -> None:
    first_page: list[str] = []
    _pdf_text(first_page, 44, 752, 20, "Linear Probing vs Separate Chaining")
    _pdf_text(first_page, 44, 729, 10, "URL shortener hash-table experiment")
    _pdf_text(first_page, 44, 697, 11, "Question and method")
    _pdf_text(
        first_page,
        44,
        680,
        9,
        "Compare lookup cost at load factors 0.1-0.9 with capacity 4093 and seed 2026.",
    )
    _pdf_text(
        first_page,
        44,
        665,
        9,
        "Both strategies use the same generated keys and misses at each load factor.",
    )
    _pdf_text(
        first_page,
        44,
        650,
        9,
        "A probe is a chain-node comparison for chaining or a slot inspection for probing.",
    )
    _pdf_text(first_page, 44, 622, 11, "Expected average probes")
    _pdf_text(first_page, 44, 604, 9, "Chaining: success = 1 + alpha/2; failure = alpha.")
    _pdf_text(
        first_page,
        44,
        589,
        9,
        "Linear probing: success ~= 0.5*(1 + 1/(1-alpha));",
    )
    _pdf_text(
        first_page,
        44,
        574,
        9,
        "failure ~= 0.5*(1 + 1/(1-alpha)^2), classic approximations.",
    )
    _pdf_text(
        first_page,
        44,
        548,
        11,
        "Measured / theory (successful and unsuccessful searches)",
    )
    headers = (
        "alpha",
        "chain success",
        "chain failure",
        "linear success",
        "linear failure",
    )
    columns = (44, 104, 207, 310, 413)
    header_y = 528
    for column, header in zip(columns, headers):
        _pdf_text(first_page, column, header_y, 7.5, header)
    _pdf_line(first_page, 44, header_y - 5, 550, header_y - 5)

    for row_index, result in enumerate(results):
        row_y = header_y - 20 - row_index * 16
        values = (
            f"{result.target_alpha:.1f}",
            f"{result.chaining_success_measured:.2f}/{result.chaining_success_theory:.2f}",
            f"{result.chaining_failed_measured:.2f}/{result.chaining_failed_theory:.2f}",
            f"{result.linear_success_measured:.2f}/{result.linear_success_theory:.2f}",
            f"{result.linear_failed_measured:.2f}/{result.linear_failed_theory:.2f}",
        )
        for column, value in zip(columns, values):
            _pdf_text(first_page, column, row_y, 7.5, value)

    high_load = results[-1]
    _pdf_text(first_page, 44, 340, 11, "Interpretation")
    _pdf_text(
        first_page,
        44,
        322,
        9,
        f"At alpha={high_load.actual_alpha:.3f}, linear probing averages",
    )
    _pdf_text(
        first_page,
        44,
        307,
        9,
        f"{high_load.linear_success_measured:.2f} successful and "
        f"{high_load.linear_failed_measured:.2f} failed probes, versus",
    )
    _pdf_text(
        first_page,
        44,
        292,
        9,
        f"{high_load.chaining_success_measured:.2f} and "
        f"{high_load.chaining_failed_measured:.2f} for chaining.",
    )
    _pdf_text(
        first_page,
        44,
        267,
        9,
        "Clustering makes linear-probing cost rise rapidly near a full table.",
    )
    _pdf_text(
        first_page,
        44,
        252,
        9,
        "Results are finite-sample observations; hash distribution can shift measured values.",
    )
    _pdf_text(
        first_page,
        44,
        40,
        8,
        "Artifacts: linear_probing_results.csv and linear_probing_results.svg",
    )

    second_page: list[str] = []
    _pdf_text(second_page, 44, 755, 16, "Lookup cost by load factor")
    _pdf_chart(second_page, results, x=42, y=402, successful=True)
    _pdf_chart(second_page, results, x=42, y=64, successful=False)
    _pdf_text(second_page, 44, 34, 8, "Solid = measured; dashed = theoretical.")

    page_contents = (
        "\n".join(first_page).encode("ascii"),
        "\n".join(second_page).encode("ascii"),
    )
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R 6 0 R] /Count 2 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        (
            f"<< /Length {len(page_contents[0])} >>\nstream\n".encode("ascii")
            + page_contents[0]
            + b"\nendstream"
        ),
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 7 0 R >>",
        (
            f"<< /Length {len(page_contents[1])} >>\nstream\n".encode("ascii")
            + page_contents[1]
            + b"\nendstream"
        ),
    ]
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for object_number, content in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{object_number} 0 obj\n".encode("ascii"))
        output.extend(content)
        output.extend(b"\nendobj\n")

    xref_offset = len(output)
    output.extend(f"xref\n0 {len(offsets)}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f\r\n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n\r\n".encode("ascii"))
    output.extend(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    PDF_PATH.write_bytes(output)


def print_table(results: list[ComparisonResult]) -> None:
    print(
        "alpha  n      chain success M/T  chain fail M/T  "
        "linear success M/T  linear fail M/T"
    )
    for result in results:
        print(
            f"{result.actual_alpha:5.3f} {result.item_count:6d} "
            f"{result.chaining_success_measured:7.3f}/{result.chaining_success_theory:6.3f} "
            f"{result.chaining_failed_measured:7.3f}/{result.chaining_failed_theory:6.3f} "
            f"{result.linear_success_measured:7.3f}/{result.linear_success_theory:6.3f} "
            f"{result.linear_failed_measured:7.3f}/{result.linear_failed_theory:6.3f}"
        )


def main() -> None:
    results = measure()
    write_csv(results)
    write_svg(results)
    write_report_pdf(results)
    print_table(results)
    print(f"\nCSV: {CSV_PATH}")
    print(f"SVG: {SVG_PATH}")
    print(f"PDF: {PDF_PATH}")


if __name__ == "__main__":
    main()
