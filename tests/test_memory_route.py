import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import routes.data as data_module


class MemoryRouteTests(unittest.TestCase):
    def _load_memory(self, l2=None, knowledge=None, evolution=None, knowledge_base=None):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            if l2 is not None:
                (tmp / "l2_short_term.json").write_text(json.dumps(l2, ensure_ascii=False), encoding="utf-8")
            if knowledge is not None:
                (tmp / "knowledge.json").write_text(json.dumps(knowledge, ensure_ascii=False), encoding="utf-8")
            if evolution is not None:
                (tmp / "evolution.json").write_text(json.dumps(evolution, ensure_ascii=False), encoding="utf-8")
            if knowledge_base is not None:
                (tmp / "knowledge_base.json").write_text(json.dumps(knowledge_base, ensure_ascii=False), encoding="utf-8")

            with patch.object(data_module.S, "PRIMARY_HISTORY_FILE", tmp / "history.json"), patch.object(
                data_module.S, "PRIMARY_STATE_DIR", tmp
            ), patch.object(data_module.S, "ensure_long_term_clean", lambda: None), patch.object(
                data_module.S,
                "normalize_event_time",
                side_effect=lambda value: str(value or "2026-03-29 00:00"),
            ), patch.object(data_module, "_is_live_skill_name", return_value=True):
                return asyncio.run(data_module.get_memory())

    def test_memory_route_surfaces_typed_l2_impressions(self):
        result = self._load_memory(
            l2=[
                {
                    "user_text": "你必须调用工具来执行操作，不要在文本里模拟执行结果",
                    "ai_text": "收到，后续我会优先走真实工具执行链。",
                    "importance": 0.92,
                    "memory_type": "rule",
                    "created_at": "2026-03-29 10:10",
                    "hit_count": 2,
                    "crystallized": False,
                },
                {
                    "user_text": "我在常州",
                    "ai_text": "记住了，后续涉及天气或本地信息会按常州来判断。",
                    "importance": 0.88,
                    "memory_type": "fact",
                    "created_at": "2026-03-29 10:20",
                    "hit_count": 0,
                    "crystallized": True,
                },
                {
                    "user_text": "今天天气",
                    "ai_text": "我来查一下。",
                    "importance": 0.4,
                    "memory_type": "general",
                    "created_at": "2026-03-29 10:30",
                },
            ]
        )

        l2_events = [item for item in result["events"] if item.get("layer") == "L2"]
        self.assertEqual(result["counts"]["L2"], 3)
        self.assertEqual(len(l2_events), 2)

        titles = {item["title"] for item in l2_events}
        self.assertEqual(titles, {"规则印象", "事实印象"})

        rule_event = next(item for item in l2_events if item["title"] == "规则印象")
        fact_event = next(item for item in l2_events if item["title"] == "事实印象")

        self.assertEqual(rule_event["meta"]["kind"], "l2_impression")
        self.assertEqual(rule_event["meta"]["memory_type"], "rule")
        self.assertEqual(rule_event["meta"]["hit_count"], 2)
        self.assertFalse(rule_event["meta"]["crystallized"])

        self.assertEqual(fact_event["meta"]["memory_type"], "fact")
        self.assertTrue(fact_event["meta"]["crystallized"])

    def test_memory_route_merges_repeated_general_l2_impressions(self):
        result = self._load_memory(
            l2=[
                {
                    "user_text": "停止监听",
                    "ai_text": "好的，我先停掉监听。",
                    "importance": 0.82,
                    "memory_type": "general",
                    "created_at": "2026-03-29 10:10",
                    "hit_count": 1,
                    "crystallized": False,
                },
                {
                    "user_text": "停止监听",
                    "ai_text": "已经停止监听了。",
                    "importance": 0.85,
                    "memory_type": "general",
                    "created_at": "2026-03-29 10:20",
                    "hit_count": 2,
                    "crystallized": True,
                },
                {
                    "user_text": "打开百度",
                    "ai_text": "我来打开百度。",
                    "importance": 0.81,
                    "memory_type": "general",
                    "created_at": "2026-03-29 10:30",
                    "hit_count": 0,
                    "crystallized": False,
                },
            ]
        )

        l2_events = [item for item in result["events"] if item.get("layer") == "L2"]
        self.assertEqual(result["counts"]["L2"], 3)
        self.assertEqual(len(l2_events), 2)

        merged_event = next(item for item in l2_events if item.get("meta", {}).get("user_text") == "停止监听")
        self.assertEqual(merged_event["title"], "对话印象")
        self.assertEqual(merged_event["meta"]["memory_type"], "general")
        self.assertEqual(merged_event["meta"]["repeat_count"], 2)
        self.assertEqual(merged_event["meta"]["hit_count"], 3)
        self.assertTrue(merged_event["meta"]["crystallized"])
        self.assertEqual(merged_event["time"], "2026-03-29 10:20")

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

    def test_memory_route_shows_only_clean_l8_knowledge_cards(self):
        result = self._load_memory(
            knowledge_base=[
                {
                    "source": "bing_rss",
                    "type": "knowledge",
                    "query": "FastAPI 是什么？",
                    "summary": "FastAPI 是一个高性能 Python Web 框架，适合构建 API 服务。",
                    "hit_count": 2,
                    "created_at": "2026-03-29 08:10",
                    "last_used": "2026-03-29 09:00",
                    "一级场景": "自主学习",
                    "二级场景": "自主学习-FastAPI",
                },
                {
                    "source": "l2_crystallize",
                    "type": "knowledge",
                    "query": "第一性原理是什么",
                    "summary": "第一性原理是从基本事实和原理出发，逐层推导解决方案的方法。",
                    "hit_count": 0,
                    "created_at": "2026-03-29 07:00",
                },
                {
                    "source": "l2_crystallize",
                    "type": "knowledge",
                    "query": "我都不知道你说的是什么意思",
                    "summary": "<think>这段对话没有知识</think>",
                    "created_at": "2026-03-29 06:00",
                },
                {
                    "source": "feedback_relearn",
                    "type": "feedback_relearn",
                    "query": "好神奇",
                    "summary": "用户问了，Nova 回复了，用户纠正了。",
                    "created_at": "2026-03-29 05:00",
                },
            ]
        )

        l8_events = [item for item in result["events"] if item.get("layer") == "L8"]
        self.assertEqual(result["counts"]["L8"], 2)
        self.assertEqual(len(l8_events), 2)

        titles = {item["title"] for item in l8_events}
        self.assertEqual(titles, {"自主学习", "对话结晶"})
        self.assertTrue(all(item.get("meta", {}).get("kind") in {"self_learned", "dialogue_crystal"} for item in l8_events))


if __name__ == "__main__":
    unittest.main()
