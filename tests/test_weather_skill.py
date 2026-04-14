import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.skills import weather


class WeatherSkillTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.history_path = Path(self._tmpdir.name) / "msg_history.json"
        self._patcher = patch.object(weather, "HISTORY_PATH", self.history_path)
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        self._tmpdir.cleanup()

    def _write_history(self, rows: list[dict]):
        self.history_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    def test_region_alias_and_explicit_city_resolve_to_urumqi(self):
        self.assertEqual(weather._extract_city("新疆的天气怎么样"), "乌鲁木齐")
        self.assertEqual(weather._extract_city("乌鲁木齐天气怎么样"), "乌鲁木齐")

    def test_follow_up_weather_query_inherits_recent_city(self):
        self._write_history(
            [
                {"role": "user", "content": "上海天气怎么样"},
                {"role": "nova", "content": "📍 上海现在 18°C，多云"},
            ]
        )

        self.assertEqual(weather._extract_city("多少度啊"), "上海")
        self.assertEqual(weather._extract_city("明天呢"), "上海")

    def test_explicit_region_query_does_not_fall_back_to_previous_city(self):
        self._write_history(
            [
                {"role": "user", "content": "上海天气怎么样"},
                {"role": "nova", "content": "📍 上海现在 18°C，多云"},
            ]
        )

        self.assertEqual(weather._extract_city("新疆天气怎么样"), "乌鲁木齐")

    def test_unknown_explicit_city_with_day_word_does_not_inherit_history(self):
        self._write_history(
            [
                {"role": "user", "content": "上海天气怎么样"},
                {"role": "nova", "content": "📍 上海现在 18°C，多云"},
            ]
        )

        self.assertEqual(weather._extract_city("成都今天天气怎么样"), "")

    def test_execute_without_city_asks_for_target_city(self):
        with patch.object(weather, "PERSONA_PATH", Path(self._tmpdir.name) / "persona.json"):
            self.assertIn("哪个城市", weather.execute("天气怎么样"))

    def test_execute_uses_profile_location_when_city_missing(self):
        persona_path = Path(self._tmpdir.name) / "persona.json"
        persona_path.write_text(
            json.dumps({"user_profile": {"location": "Seattle"}}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        with patch.object(weather, "PERSONA_PATH", persona_path), patch.object(
            weather, "_resolve_city_coords", return_value=("Seattle", (47.61, -122.33))
        ), patch.object(weather, "get_weather", return_value="📍 Seattle现在 12°C，多云"), patch.object(
            weather, "get_forecast_window", return_value="Seattle今天天气：\n📍 今天：8~14°C，多云"
        ):
            reply = weather.execute("天气怎么样")

        self.assertIn("Seattle", reply)

    def test_execute_uses_user_location_context_when_city_missing(self):
        with patch.object(
            weather, "_resolve_city_coords", return_value=("Bay Area", (37.77, -122.42))
        ), patch.object(weather, "get_weather", return_value="📍 Bay Area现在 15°C，多云"), patch.object(
            weather, "get_forecast_window", return_value="Bay Area今天天气：\n📍 今天：10~17°C，多云"
        ):
            reply = weather.execute("天气怎么样", {"user_location": "Bay Area"})

        self.assertIn("Bay Area", reply)


if __name__ == "__main__":
    unittest.main()
