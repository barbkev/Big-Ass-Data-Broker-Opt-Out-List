#!/usr/bin/env python3
"""CLI for working with the structured broker inventory."""

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Iterable, List, Dict, Any


PRIORITY_ORDER = {
    "crucial": 0,
    "high": 1,
    "normal": 2,
}


def parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "y"}:
        return True
    if normalized in {"false", "0", "no", "n"}:
        return False
    raise argparse.ArgumentTypeError(f"Invalid boolean value: {value}")


def load_inventory(path: Path) -> List[Dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Inventory file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Inventory file is not valid JSON: {path}") from exc

    if not isinstance(data, list):
        raise SystemExit("Inventory file must contain a list of brokers.")
    return data


def filter_inventory(
    brokers: Iterable[Dict[str, Any]],
    priority: str | None,
    requires_phone: bool | None,
    requires_id: bool | None,
    requires_payment: bool | None,
    category: str | None,
) -> List[Dict[str, Any]]:
    filtered = []
    for broker in brokers:
        if priority and broker.get("priority") != priority:
            continue
        if requires_phone is not None and broker.get("requires_phone") is not requires_phone:
            continue
        if requires_id is not None and broker.get("requires_id") is not requires_id:
            continue
        if requires_payment is not None and broker.get("requires_payment") is not requires_payment:
            continue
        if category and broker.get("category") != category:
            continue
        filtered.append(broker)
    return filtered


def sort_brokers(brokers: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(
        brokers,
        key=lambda broker: (PRIORITY_ORDER.get(broker.get("priority"), 99), broker.get("name", "")),
    )


def render_table(brokers: Iterable[Dict[str, Any]]) -> str:
    rows = [
        [
            "Name",
            "Priority",
            "Requires Phone",
            "Requires ID",
            "Requires Payment",
            "Category",
        ]
    ]
    for broker in brokers:
        rows.append(
            [
                broker.get("name", ""),
                broker.get("priority", ""),
                str(broker.get("requires_phone", False)).lower(),
                str(broker.get("requires_id", False)).lower(),
                str(broker.get("requires_payment", False)).lower(),
                broker.get("category", ""),
            ]
        )

    col_widths = [max(len(row[idx]) for row in rows) for idx in range(len(rows[0]))]
    lines = []
    for row_index, row in enumerate(rows):
        padded = [value.ljust(col_widths[idx]) for idx, value in enumerate(row)]
        line = " | ".join(padded)
        lines.append(line)
        if row_index == 0:
            separator = " | ".join("-" * width for width in col_widths)
            lines.append(separator)
    return "\n".join(lines)


def export_csv(brokers: Iterable[Dict[str, Any]], output: Path | None) -> None:
    fieldnames = [
        "name",
        "priority",
        "category",
        "requires_phone",
        "requires_id",
        "requires_payment",
        "opt_out_url",
    ]
    rows = list(brokers)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
    else:
        writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def export_json(brokers: Iterable[Dict[str, Any]], output: Path | None) -> None:
    payload = list(brokers)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    else:
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")


def add_filter_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--priority",
        choices=sorted(PRIORITY_ORDER.keys(), key=PRIORITY_ORDER.get),
        help="Filter by priority (crucial, high, normal).",
    )
    parser.add_argument(
        "--requires-phone",
        type=parse_bool,
        help="Filter by whether a broker requires a phone call (true/false).",
    )
    parser.add_argument(
        "--requires-id",
        type=parse_bool,
        help="Filter by whether a broker requires an ID upload (true/false).",
    )
    parser.add_argument(
        "--requires-payment",
        type=parse_bool,
        help="Filter by whether a broker requires payment (true/false).",
    )
    parser.add_argument(
        "--category",
        help="Filter by inventory category (e.g., people_search).",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Opt-out inventory CLI")
    parser.add_argument(
        "--inventory",
        type=Path,
        default=Path("data/brokers.json"),
        help="Path to the broker inventory JSON file.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List all brokers")
    add_filter_args(list_parser)

    filter_parser = subparsers.add_parser("filter", help="Filter brokers")
    add_filter_args(filter_parser)

    export_parser = subparsers.add_parser("export", help="Export a to-do queue")
    export_parser.add_argument(
        "--format",
        choices=["csv", "json"],
        default="csv",
        help="Export format (csv or json).",
    )
    export_parser.add_argument(
        "--output",
        type=Path,
        help="Optional output path (defaults to stdout).",
    )
    add_filter_args(export_parser)

    args = parser.parse_args()
    brokers = load_inventory(args.inventory)
    filtered = filter_inventory(
        brokers,
        priority=getattr(args, "priority", None),
        requires_phone=getattr(args, "requires_phone", None),
        requires_id=getattr(args, "requires_id", None),
        requires_payment=getattr(args, "requires_payment", None),
        category=getattr(args, "category", None),
    )
    ordered = sort_brokers(filtered)

    if args.command in {"list", "filter"}:
        print(render_table(ordered))
        return

    if args.command == "export":
        if args.format == "csv":
            export_csv(ordered, args.output)
        else:
            export_json(ordered, args.output)
        return

    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
