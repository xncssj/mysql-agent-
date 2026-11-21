#!/usr/bin/env python3
"""CLI for MySQL orchestrator."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from mysql_agent.orchestrator import AgentBundle, MySQLOrchestrator


def main() -> None:
    parser = argparse.ArgumentParser(description="Run MySQL diagnosis orchestrator")
    parser.add_argument("--query", required=True, help="User query")
    parser.add_argument("--context", help="JSON context with sql/anomalies/metrics/etc")
    parser.add_argument("--index-path", help="Optional vector index path for RAG")
    args = parser.parse_args()

    context = json.loads(args.context) if args.context else {}
    if context.get("innodb_status_file"):
        context["innodb_status_file"] = str(Path(context["innodb_status_file"]).expanduser())

    bundle = AgentBundle.create_default(index_path=args.index_path)
    orchestrator = MySQLOrchestrator(bundle)
    result = orchestrator.run(args.query, context=context)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
