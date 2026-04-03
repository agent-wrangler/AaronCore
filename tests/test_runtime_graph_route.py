import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import routes.data as data_module


class RuntimeGraphRouteTests(unittest.TestCase):
    def _write(self, root: Path, relative_path: str, content: str):
        target = root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def test_runtime_graph_builds_static_map_and_recent_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._write(root, "agent_final.py", "from routes import data\n")
            self._write(root, "routes/data.py", 'from core import shared\n@router.get("/memory")\ndef x():\n    return {}\n')
            self._write(root, "core/shared.py", "VALUE = 1\n")
            self._write(
                root,
                "output.html",
                '<link rel="stylesheet" href="/static/css/main.css">\n<script src="/static/js/app.js"></script>\n',
            )
            self._write(root, "static/js/app.js", "import './graph.js';\nfetch('/memory')\n")
            self._write(root, "static/js/graph.js", "console.log('graph');\n")
            self._write(root, "static/css/main.css", "body{color:#111;}\n")
            self._write(root, "state_data/should_hide.py", "print('ignore')\n")

            repo_file = str(root / "routes" / "data.py").replace("/", "\\")
            history = [
                {
                    "role": "nova",
                    "time": "2026-03-31T08:00:00",
                    "content": "我先看一下项目结构。",
                    "process": {
                        "steps": [
                            {"label": "模型思考", "detail": "我先看看项目结构", "status": "done"},
                            {"label": "记忆就绪", "detail": "recall_memory · 【对话记忆】 / · 记住目标目录", "status": "done"},
                            {"label": "技能完成", "detail": "folder_explore · 已确认目录：C:\\Users\\36459\\NovaNotes", "status": "done"},
                            {"label": "技能完成", "detail": f"read_file · {repo_file} / <think>", "status": "done"},
                            {"label": "技能失败", "detail": "run_command · 本地命令执行失败", "status": "error"},
                        ]
                    },
                }
            ]

            with patch.object(data_module.S, "ENGINE_DIR", root), patch.object(
                data_module.S,
                "load_msg_history",
                lambda: history,
            ):
                result = asyncio.run(data_module.get_runtime_graph(limit=6))

        node_ids = {node["id"] for node in result["nodes"]}
        node_map = {node["id"]: node for node in result["nodes"]}
        edge_set = {(edge["source"], edge["target"], edge["kind"]) for edge in result["edges"]}

        self.assertIn("agent_final.py", node_ids)
        self.assertIn("routes/data.py", node_ids)
        self.assertIn("output.html", node_ids)
        self.assertIn("static/js/app.js", node_ids)
        self.assertIn("tool:folder_explore", node_ids)
        self.assertNotIn("state_data/should_hide.py", node_ids)

        self.assertIn(("agent_final.py", "routes/data.py", "import"), edge_set)
        self.assertIn(("output.html", "static/js/app.js", "asset"), edge_set)
        self.assertIn(("static/js/app.js", "routes/data.py", "api"), edge_set)
        self.assertEqual(node_map["agent_final.py"]["subtitle"], "后端主入口")
        self.assertEqual(node_map["routes/data.py"]["subtitle"], "数据路由")
        self.assertEqual(node_map["static/js/app.js"]["subtitle"], "主页面控制脚本")

        self.assertEqual(result["summary"]["file_count"], 7)
        self.assertEqual(len(result["runs"]), 1)
        run = result["runs"][0]
        self.assertEqual(run["status"], "error")
        self.assertIn("runtime:user", run["node_ids"])
        self.assertIn("runtime:reply", run["node_ids"])
        self.assertIn("tool:folder_explore", run["node_ids"])
        self.assertIn("routes/data.py", run["node_ids"])
        self.assertEqual(len(run["external_nodes"]), 1)

    def test_runtime_graph_matches_route_prefixes_from_frontend_calls(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._write(root, "routes/lab.py", '@router.post("/lab/start/{exp_id}")\ndef x():\n    return {}\n')
            self._write(root, "static/js/lab.js", "fetch('/lab/start/' + expId, {method:'POST'})\n")

            with patch.object(data_module.S, "ENGINE_DIR", root), patch.object(
                data_module.S,
                "load_msg_history",
                lambda: [],
            ):
                result = asyncio.run(data_module.get_runtime_graph(limit=2))

        edge_set = {(edge["source"], edge["target"], edge["kind"]) for edge in result["edges"]}
        self.assertIn(("static/js/lab.js", "routes/lab.py", "api"), edge_set)

    def test_runtime_graph_ignores_root_only_asset_refs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._write(root, "output.html", '<a href="/">home</a>\n<script src="/static/js/app.js"></script>\n')
            self._write(root, "static/js/app.js", "console.log('ok')\n")

            with patch.object(data_module.S, "ENGINE_DIR", root), patch.object(
                data_module.S,
                "load_msg_history",
                lambda: [],
            ):
                result = asyncio.run(data_module.get_runtime_graph(limit=2))

        node_ids = {node["id"] for node in result["nodes"]}
        self.assertIn("output.html", node_ids)
        self.assertIn("static/js/app.js", node_ids)
