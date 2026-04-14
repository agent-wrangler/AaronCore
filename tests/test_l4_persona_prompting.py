import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from decision import reply_prompts
from storage import state_loader


class L4PersonaPromptingTests(unittest.TestCase):
    def test_load_l4_persona_keeps_flat_fields_and_local_persona(self):
        persona = {
            "active_mode": "sweet",
            "persona_modes": {
                "sweet": {
                    "style_prompt": "自然黏人，像熟悉的小助理。",
                    "tone": ["活泼", "自然"],
                }
            },
            "user_profile": {
                "identity": "用户是主人",
                "city": "常州",
            },
            "interaction_rules": ["不要假装执行", "叫我主人"],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            persona_file = Path(tmpdir) / "persona.json"
            persona_file.write_text(json.dumps(persona, ensure_ascii=False), encoding="utf-8")

            with patch.object(state_loader, "PERSONA_FILE", persona_file):
                loaded = state_loader.load_l4_persona()

        self.assertEqual(loaded.get("active_mode"), "sweet")
        self.assertIn("persona_modes", loaded)
        self.assertEqual((loaded.get("user_profile") or {}).get("city"), "常州")
        self.assertEqual((loaded.get("local_persona") or {}).get("active_mode"), "sweet")
        self.assertEqual(loaded.get("style_rules"), ["不要假装执行", "叫我主人"])

    def test_build_style_hints_reads_nested_local_persona(self):
        l4 = {
            "local_persona": {
                "active_mode": "sweet",
                "persona_modes": {
                    "sweet": {
                        "style_prompt": "自然黏人，像熟悉的小助理。",
                        "tone": ["活泼", "自然"],
                        "particles": ["呀", "啦"],
                    }
                },
            }
        }

        hints = reply_prompts.build_style_hints_from_l4(l4)

        self.assertIn("自然黏人", hints)
        self.assertIn("语气关键词", hints)
        self.assertIn("活泼", hints)
        self.assertIn("常用语气词", hints)

    def test_condense_l4_includes_user_preference_and_dislike(self):
        l4 = {
            "local_persona": {
                "ai_profile": {"identity": "我是 Nova。"},
                "user_profile": {
                    "identity": "用户是主人",
                    "preference": "喜欢自然一点、别太模板化",
                    "dislike": "不喜欢废话和重复确认",
                    "city": "常州",
                },
                "relationship_profile": {"relationship": "长期熟悉的搭档"},
            }
        }

        text = reply_prompts.condense_l4(l4)

        self.assertIn("用户：用户是主人", text)
        self.assertIn("用户偏好：喜欢自然一点、别太模板化", text)
        self.assertIn("用户反感：不喜欢废话和重复确认", text)
        self.assertIn("用户所在位置：常州", text)


if __name__ == "__main__":
    unittest.main()
