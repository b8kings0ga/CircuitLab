#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from _platform import ComponentRegistry, HilEngine, default_data_root


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the CircuitLab software HIL state machine.")
    parser.add_argument("--data", type=Path, default=default_data_root())
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("request", type=Path)
    arm = sub.add_parser("arm")
    arm.add_argument("job_id")
    arm.add_argument("nonce")
    run = sub.add_parser("run")
    run.add_argument("job_id")
    run.add_argument("--fault")
    abort = sub.add_parser("abort")
    abort.add_argument("job_id")
    status = sub.add_parser("status")
    status.add_argument("job_id", nargs="?")
    args = parser.parse_args()
    root = args.data.expanduser().resolve()
    engine = HilEngine(root / "hil", ComponentRegistry(root / "registry"))
    if args.command == "prepare":
        result = engine.prepare(json.loads(args.request.read_text(encoding="utf-8")))
    elif args.command == "arm":
        result = engine.arm(args.job_id, args.nonce, True)
    elif args.command == "run":
        result = engine.run(args.job_id, {"fault": args.fault})
    elif args.command == "abort":
        result = engine.abort(args.job_id)
    else:
        result = engine.status(args.job_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

