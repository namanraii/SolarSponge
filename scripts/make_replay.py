#!/usr/bin/env python3
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from solarsponge.config import load_config
from solarsponge.loop import build_demo
from solarsponge.store import Store


if __name__ == "__main__":
    settings = load_config()
    store = Store(settings)
    replay = build_demo(settings, store)
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/replay.json").write_text(json.dumps(replay, default=str))
    print("solver", replay["plan"]["solver_status"])
    print(json.dumps(replay["kpis"], indent=2))
