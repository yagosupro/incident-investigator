"""CLI entry point for the local end-to-end demo."""

from __future__ import annotations

import argparse
import json

from .backend import SCENARIOS, SimulatedBackend
from .investigator import Investigator
from .model_loop import ModelInvestigationLoop
from .ollama import OllamaLocalAdapter
from .tools import ReadOnlyTools


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a local incident investigation demo.")
    parser.add_argument("command", choices=["demo", "agent"])
    parser.add_argument("--scenario", choices=sorted(SCENARIOS), default="slow")
    parser.add_argument("--model", help="Required for agent; name of a model already available in local Ollama.")
    parser.add_argument("--max-steps", type=int, default=8, help="Maximum local-model decisions for agent mode.")
    args = parser.parse_args()
    if args.command == "agent" and not args.model:
        parser.error("agent requires --model NAME")
    if args.max_steps < 1:
        parser.error("--max-steps must be positive")
    with SimulatedBackend() as backend:
        tools = ReadOnlyTools(backend.base_url)
        if args.command == "demo":
            report = Investigator(tools).investigate(args.scenario)
        else:
            report = ModelInvestigationLoop(
                tools, OllamaLocalAdapter(args.model), max_steps=args.max_steps
            ).investigate(args.scenario)
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    return 0 if args.command == "demo" or report.outcome == "model_final" else 1


if __name__ == "__main__":
    raise SystemExit(main())
