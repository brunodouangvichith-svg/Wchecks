"""
CLI de consultation et de déclenchement ponctuel de l'agent de veille.

Usage :
    python cli.py --latest spr_stocks
    python cli.py --history 10 brent_prices
    python cli.py --minerals-refresh
"""

import argparse

from rich.console import Console
from rich.table import Table

from logging_config import configure_logging

console = Console()


def cmd_latest(table_name: str) -> None:
    from clients.neon_client import get_latest

    row = get_latest(table_name)
    if row is None:
        console.print(f"[yellow]Aucune donnée dans la collection '{table_name}'.[/yellow]")
        return
    _print_rows(table_name, [row])


def cmd_history(table_name: str, n: int) -> None:
    from clients.neon_client import get_history

    rows = get_history(table_name, n)
    if not rows:
        console.print(f"[yellow]Aucune donnée dans la collection '{table_name}'.[/yellow]")
        return
    _print_rows(table_name, rows)


def _print_rows(table_name: str, rows: list[dict]) -> None:
    table = Table(title=table_name)
    for col in rows[0].keys():
        table.add_column(col)
    for row in rows:
        table.add_row(*(str(v) for v in row.values()))
    console.print(table)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CLI de veille énergétique et géopolitique")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--latest", metavar="COLLECTION", help="Affiche la dernière ligne d'une collection")
    group.add_argument(
        "--history", nargs=2, metavar=("N", "COLLECTION"), help="Affiche les N dernières lignes d'une collection"
    )
    group.add_argument(
        "--minerals-refresh", action="store_true",
        help="Déclenche manuellement la collecte des minerais stratégiques (USGS)",
    )
    return parser


def main() -> None:
    configure_logging()
    parser = build_parser()
    args = parser.parse_args()

    if args.latest:
        cmd_latest(args.latest)
    elif args.history:
        n, table_name = args.history
        cmd_history(table_name, int(n))
    elif args.minerals_refresh:
        from collectors.collect_minerals import run

        run()


if __name__ == "__main__":
    main()
