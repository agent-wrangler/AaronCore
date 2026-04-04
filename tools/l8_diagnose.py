import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from memory import l8_learning as l8_learn


def main():
    parser = argparse.ArgumentParser(description="Diagnose NovaCore L8 auto-learn decisions.")
    parser.add_argument("--query", required=True, help="User message to inspect.")
    parser.add_argument("--route-mode", default="chat", help="Route mode to simulate, e.g. chat/skill/hybrid.")
    parser.add_argument("--skill", default="none", help="Skill name to simulate alongside the route mode.")
    parser.add_argument("--run", action="store_true", help="Actually run auto_learn instead of dry-run diagnosis.")
    parser.add_argument("--limit", type=int, default=3, help="How many knowledge hits to display.")
    args = parser.parse_args()

    route_result = {"mode": args.route_mode, "skill": args.skill}
    config = l8_learn.load_autolearn_config()
    hits = l8_learn.find_relevant_knowledge(args.query, limit=max(args.limit, 1), touch=False)
    should_run, reason = l8_learn.should_trigger_auto_learn(
        args.query,
        route_result=route_result,
        has_relevant_knowledge=bool(hits),
        config=config,
    )

    payload = {
        "query": args.query,
        "route_result": route_result,
        "config": config,
        "should_trigger": should_run,
        "reason": reason,
        "knowledge_hits": hits,
    }

    if args.run:
        payload["auto_learn_result"] = l8_learn.auto_learn(args.query, route_result=route_result)

    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
