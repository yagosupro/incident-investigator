"""CLI entry point for the local end-to-end demo."""

from __future__ import annotations

import argparse
import json

from .backend import SCENARIOS, SimulatedBackend
from .investigator import Investigator
from .tools import ReadOnlyTools


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a local, deterministic incident investigation demo.")
    parser.add_argument("command", choices=["demo"])
    parser.add_argument("--scenario", choices=sorted(SCENARIOS), default="slow")
    args = parser.parse_args()
    with SimulatedBackend() as backend:
        report = Investigator(ReadOnlyTools(backend.base_url)).investigate(args.scenario)
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
