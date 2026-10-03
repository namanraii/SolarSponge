"""CLI: demo, eval, serve, backtest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from solarsponge.config import load_config


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="solarsponge")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("demo", help="Build a deterministic one-day replay and print KPIs")
    ev = sub.add_parser("eval", help="Run scenario evaluation and write artifacts")
    ev.add_argument("--days", type=int, default=None)
    ev.add_argument("--out", default="artifacts")
    sub.add_parser("backtest", help="Rolling-origin forecast backtest")
    sv = sub.add_parser("serve", help="Run the API")
    sv.add_argument("--host", default="0.0.0.0")
    sv.add_argument("--port", type=int, default=8000)
    sub.add_parser("hash", help="Print config hash")

    args = p.parse_args(argv)
    settings = load_config()

    if args.cmd == "hash":
        print(settings.config_hash())
        return 0

    if args.cmd == "demo":
        from solarsponge.loop import build_demo
        from solarsponge.store import Store

        store = Store(settings)
        replay = build_demo(settings, store)
        print(json.dumps(replay["kpis"], indent=2))
        print("solver", replay["plan"]["solver_status"], "hash", replay["config_hash"])
        Path("artifacts").mkdir(exist_ok=True)
        Path("artifacts/replay.json").write_text(json.dumps(replay, default=str))
        return 0

    if args.cmd == "eval":
        from solarsponge.kpi.report import run_evaluation, write_report

        result = run_evaluation(settings, n_days=args.days)
        path = write_report(result, Path(args.out))
        print(path)
        print(json.dumps(result["summary"], indent=2, default=str))
        return 0

    if args.cmd == "backtest":
        from solarsponge.forecasting.backtest import run_backtest

        print(json.dumps(run_backtest(settings), indent=2))
        return 0

    if args.cmd == "serve":
        import uvicorn

        uvicorn.run("solarsponge.api.app:app", host=args.host, port=args.port, reload=False)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
