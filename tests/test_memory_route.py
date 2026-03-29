import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import routes.data as data_module


class MemoryRouteTests(unittest.TestCase):
    def _load_memory(self, knowledge=None, evolution=None):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            if knowledge is not None:
                (tmp / "knowledge.json").write_text(json.dumps(knowledge, ensure_ascii=False), encoding="utf-8")
            if evolution is not None:
                (tmp / "evolution.json").write_text(json.dumps(evolution, ensure_ascii=False), encoding="utf-8")

            with patch.object(data_module.S, "PRIMARY_HISTORY_FILE", tmp / "history.json"), patch.object(
                data_module.S, "PRIMARY_STATE_DIR", tmp
            ), patch.object(data_module.S, "ensure_long_term_clean", lambda: None), patch.object(
                data_module.S,
                "normalize_event_time",
                side_effect=lambda value: str(value or "2026-03-29 00:00"),
            ), patch.object(data_module, "_is_live_skill_name", return_value=True):
                return asyncio.run(data_module.get_memory())

    def test_memory_route_surfaces_l5_method_experience_and_ability_hint(self):
        result = self._load_memory(
            knowledge=[
                {
                    "name": "open_target",
                    "source": "l6_success_path",
                    "summary": "先定位窗口，再打开目标目录",
                    "success_count": 3,
                    "learned_at": "2026-03-29 10:30",
                },
                {
                    "name": "web_search",
                    "source": "skill_registry",
                    "learned_at": "2026-03-29 09:00",
                },
            ]
        )

        l5_events = [item for item in result["events"] if item.get("layer") == "L5"]
        self.assertEqual(result["counts"]["L5"], 2)
        self.assertEqual(len(l5_events), 2)

        method_event = next(item for item in l5_events if item.get("meta", {}).get("kind") == "method_experience")
        ability_event = next(item for item in l5_events if item.get("meta", {}).get("kind") == "ability_hint")

        self.assertEqual(method_event["title"], "方法经验")
        self.assertEqual(method_event["meta"]["skill"], "open_target")
        self.assertEqual(method_event["meta"]["success_count"], 3)

        self.assertEqual(ability_event["title"], "能力线索")
        self.assertEqual(ability_event["meta"]["skill"], "web_search")
        self.assertEqual(ability_event["meta"]["visible_count"], 2)

    def test_memory_route_prefers_l6_skill_runs_as_execution_trace(self):
        result = self._load_memory(
            evolution={
                "skill_runs": [
                    {
                        "skill": "open_target",
                        "at": "2026-03-29 11:20",
                        "summary": "已打开项目目录",
                        "verified": True,
                        "observed_state": "folder_opened",
                        "drift_reason": "",
                    }
                ],
                "skills_used": {},
            }
        )

        l6_events = [item for item in result["events"] if item.get("layer") == "L6"]
        self.assertEqual(result["counts"]["L6"], 1)
        self.assertEqual(len(l6_events), 1)

        trace_event = l6_events[0]
        self.assertEqual(trace_event["title"], "执行轨迹")
        self.assertEqual(trace_event["event_type"], "execution_trace")
        self.assertEqual(trace_event["meta"]["kind"], "execution_trace")
        self.assertEqual(trace_event["meta"]["skill"], "open_target")
        self.assertEqual(trace_event["meta"]["verified"], True)
        self.assertEqual(trace_event["meta"]["observed_state"], "folder_opened")

    def test_memory_route_falls_back_to_execution_count_when_skill_runs_missing(self):
        result = self._load_memory(
            evolution={
                "skills_used": {
                    "web_search": {
                        "count": 2,
                        "last_used": "2026-03-29 08:10",
                    }
                }
            }
        )

        l6_events = [item for item in result["events"] if item.get("layer") == "L6"]
        self.assertEqual(result["counts"]["L6"], 1)
        self.assertEqual(len(l6_events), 1)

        trace_event = l6_events[0]
        self.assertEqual(trace_event["title"], "执行轨迹")
        self.assertEqual(trace_event["event_type"], "execution_trace")
        self.assertEqual(trace_event["meta"]["kind"], "execution_count")
        self.assertEqual(trace_event["meta"]["skill"], "web_search")
        self.assertEqual(trace_event["meta"]["count"], 2)


if __name__ == "__main__":
    unittest.main()
