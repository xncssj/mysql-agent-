#!/usr/bin/env python3
"""Load Phase-1 mysql_kg.json into Neo4j (optional Phase 2)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mysql_agent.kg import Neo4jKGClient


def main() -> None:
    parser = argparse.ArgumentParser(description="Load MySQL KG into Neo4j")
    parser.add_argument("--kg", default=str(Path(__file__).resolve().parents[1] / "data/kg/mysql_kg.json"))
    parser.add_argument("--ping-only", action="store_true")
    args = parser.parse_args()

    client = Neo4jKGClient()
    try:
        ok = client.ping()
        print({"ping": ok, "uri": client.uri})
        if args.ping_only:
            return
        stats = client.load_kg_file(args.kg)
        print({"loaded": stats})
    finally:
        client.close()


if __name__ == "__main__":
    main()
