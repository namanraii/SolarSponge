#!/usr/bin/env python3
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from solarsponge.config import load_config
from solarsponge.forecasting.backtest import run_backtest


if __name__ == "__main__":
    print(json.dumps(run_backtest(load_config()), indent=2))
