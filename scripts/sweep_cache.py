"""Sweep `cache:` parameters on tape C1 over several seeds (used for report section 8).

    python scripts/sweep_cache.py --thresholds 0.80,0.92,0.97 --ttls 60 --stales 300
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import argparse
import itertools

from gameday_lab.cache import CachingClient, SemanticCache
from gameday_lab.factory import build_client
from gameday_lab.sim.config import load_config
from gameday_lab.sim.engine import evaluate_checks, run_scenario


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--thresholds", default="0.92")
    ap.add_argument("--ttls", default="60")
    ap.add_argument("--stales", default="300")
    ap.add_argument("--seeds", default="25,26,27")
    ap.add_argument("--config", default="configs/gameday.yaml")
    ap.add_argument("--scenarios", default="configs/scenarios_cache.yaml")
    args = ap.parse_args()
    cfg = load_config(args.config, args.scenarios)
    key = next(iter(cfg.scenarios))
    seeds = [int(x) for x in args.seeds.split(",")]
    print(f"{'thr':>5} {'ttl':>5} {'stale':>5} | seed  faq_av  hit  stale wrong outdated cost  reasons / failed")
    for thr, ttl, stale in itertools.product(*(map(float, a.split(",")) for a in (args.thresholds, args.ttls, args.stales))):
        for seed in seeds:
            cache = SemanticCache(similarity_threshold=thr, ttl_s=ttl, max_stale_s=stale,
                                  max_entries=int(cfg.cache.get("max_entries", 500)))
            client = CachingClient(build_client("resilient", cfg, seed), cache)
            m = run_scenario(cfg, key, client, seed).metrics()
            failed = [k for k, v in evaluate_checks(m, cfg.scenarios[key].checks).items() if not v]
            print(f"{thr:5.2f} {ttl:5.0f} {stale:5.0f} | {seed:4d} {m['faq_availability']:7.4f} {m['cache_hit_ratio']:5.3f} "
                  f"{m['stale_served']:5d} {m['wrong_answers']:5d} {m['outdated_answers']:8d} {m['cost_per_good_turn']:5.3f}  "
                  f"{m['wrong_answers_by_reason']} {'PASS' if not failed else 'FAIL ' + ','.join(failed)}")


if __name__ == "__main__":
    main()
