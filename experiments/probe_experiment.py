"""Compare separate-chaining lookup costs with the Chapter 08 estimates."""

import csv
import math
import random
from pathlib import Path
from typing import NamedTuple
from xml.sax.saxutils import escape

from src.hash_table import HashTable

CAPACITY = 4093
RANDOM_SEED = 2026
LOAD_FACTORS = tuple(step / 4 for step in range(1, 17))
OUTPUT_DIR = Path(__file__).resolve().parent
CSV_PATH = OUTPUT_DIR / "results.csv"
SVG_PATH = OUTPUT_DIR / "results.svg"


class ProbeResult(NamedTuple):
    target_alpha: float
    actual_alpha: float
    item_count: int
    successful_average: float
    successful_theory: float
    failed_average: float
    failed_theory: float


def random_url(rng: random.Random, label: str, index: int) -> str:
    token = rng.getrandbits(64)
    return f"https://{label}-{token:016x}.example/{index}"


def measure() -> list[ProbeResult]:
    rng = random.Random(RANDOM_SEED)
    results = []

    for target_alpha in LOAD_FACTORS:
        item_count = int(target_alpha * CAPACITY + 0.5)
        actual_alpha = item_count / CAPACITY
        table = HashTable(capacity=CAPACITY, max_load=None)
        urls = [
            random_url(rng, "short", index)
            for index in range(item_count)
        ]

        for index, url in enumerate(urls):
            table.put(url, str(index))

        successful_comparisons = 0
        for index, url in enumerate(urls):
            value, comparisons = table.get_with_comparisons(url)
            if value != str(index):
                raise RuntimeError(f"successful lookup failed for {url!r}")
            successful_comparisons += comparisons

        failed_comparisons = 0
        for index in range(item_count):
            url = random_url(rng, "missing", index)
            value, comparisons = table.get_with_comparisons(url)
            if value is not None:
                raise RuntimeError(f"failed lookup unexpectedly found {url!r}")
            failed_comparisons += comparisons

        results.append(
            ProbeResult(
                target_alpha=target_alpha,
                actual_alpha=actual_alpha,
                item_count=item_count,
                successful_average=successful_comparisons / item_count,
                successful_theory=1 + actual_alpha / 2,
                failed_average=failed_comparisons / item_count,
                failed_theory=actual_alpha,
            )
        )

    return results


def write_csv(results: list[ProbeResult]) -> None:
    with CSV_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(
            (
                "target_alpha",
                "actual_alpha",
                "capacity",
                "item_count",
                "successful_measured",
                "successful_theory_1_plus_alpha_over_2",
                "failed_measured",
                "failed_theory_alpha",
            )
        )
        for result in results:
            writer.writerow(
                (
                    f"{result.target_alpha:.2f}",
                    f"{result.actual_alpha:.6f}",
                    CAPACITY,
                    result.item_count,
                    f"{result.successful_average:.6f}",
                    f"{result.successful_theory:.6f}",
                    f"{result.failed_average:.6f}",
                    f"{result.failed_theory:.6f}",
                )
            )


def write_svg(results: list[ProbeResult]) -> None:
    width, height = 1100, 620
    left, top, plot_width, plot_height = 88, 56, 720, 440
    x_max = 4.0
    measured_values = [
        value
        for result in results
        for value in (
            result.successful_average,
            result.successful_theory,
            result.failed_average,
            result.failed_theory,
        )
    ]
    y_max = max(1, math.ceil(max(measured_values)))

    def x_position(alpha: float) -> float:
        return left + alpha / x_max * plot_width

    def y_position(value: float) -> float:
        return top + (y_max - value) / y_max * plot_height

    series = (
        ("Success measured", "#1769aa", "successful_average", ""),
        ("Success theory: 1 + α/2", "#1769aa", "successful_theory", "8 5"),
        ("Failure measured", "#d1495b", "failed_average", ""),
        ("Failure theory: α", "#d1495b", "failed_theory", "8 5"),
    )
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<title>Average hash-table nodes compared by load factor</title>",
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="550" y="30" text-anchor="middle" font-family="sans-serif" font-size="20">Separate chaining: measured and theoretical lookup cost</text>',
    ]

    for tick in range(y_max + 1):
        y = y_position(float(tick))
        parts.extend(
            (
                f'<line x1="{left}" y1="{y:.2f}" x2="{left + plot_width}" y2="{y:.2f}" stroke="#dddddd"/>',
                f'<text x="{left - 12}" y="{y + 5:.2f}" text-anchor="end" font-family="sans-serif" font-size="13">{tick}</text>',
            )
        )

    for tick in range(9):
        alpha = tick / 2
        x = x_position(alpha)
        parts.extend(
            (
                f'<line x1="{x:.2f}" y1="{top + plot_height}" x2="{x:.2f}" y2="{top + plot_height + 5}" stroke="#333"/>',
                f'<text x="{x:.2f}" y="{top + plot_height + 24}" text-anchor="middle" font-family="sans-serif" font-size="13">{alpha:g}</text>',
            )
        )

    parts.extend(
        (
            f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" stroke="#333"/>',
            f'<line x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top + plot_height}" stroke="#333"/>',
            f'<text x="{left + plot_width / 2:.2f}" y="{top + plot_height + 55}" text-anchor="middle" font-family="sans-serif" font-size="15">Load factor α</text>',
            f'<text x="22" y="{top + plot_height / 2:.2f}" transform="rotate(-90 22 {top + plot_height / 2:.2f})" text-anchor="middle" font-family="sans-serif" font-size="15">Average nodes compared</text>',
        )
    )

    for label, color, attribute, dash in series:
        points = " ".join(
            f"{x_position(result.actual_alpha):.2f},{y_position(getattr(result, attribute)):.2f}"
            for result in results
        )
        dash_attribute = f' stroke-dasharray="{dash}"' if dash else ""
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
    for index, (label, color, _, dash) in enumerate(series):
        y = top + 36 + index * 34
        dash_attribute = f' stroke-dasharray="{dash}"' if dash else ""
        parts.extend(
            (
                f'<line x1="{legend_x}" y1="{y}" x2="{legend_x + 34}" y2="{y}" stroke="{color}" stroke-width="2.5"{dash_attribute}/>',
                f'<text x="{legend_x + 44}" y="{y + 5}" font-family="sans-serif" font-size="13">{escape(label)}</text>',
            )
        )

    parts.append("</svg>")
    SVG_PATH.write_text("\n".join(parts) + "\n", encoding="utf-8")


def print_table(results: list[ProbeResult]) -> None:
    print(
        "α(target) α(actual) n      success(measured/theory) "
        "failure(measured/theory)"
    )
    for result in results:
        print(
            f"{result.target_alpha:8.2f} {result.actual_alpha:8.4f} "
            f"{result.item_count:6d} "
            f"{result.successful_average:8.3f}/{result.successful_theory:6.3f} "
            f"{result.failed_average:8.3f}/{result.failed_theory:6.3f}"
        )


def main() -> None:
    results = measure()
    write_csv(results)
    write_svg(results)
    print_table(results)
    print(f"\nCSV: {CSV_PATH}")
    print(f"SVG: {SVG_PATH}")


if __name__ == "__main__":
    main()
