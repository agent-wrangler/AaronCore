# -*- coding: utf-8 -*-
"""测试 v2 交互阶段识别 + 语气理解层 + 向后兼容"""

import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.router import (
    classify_stage, classify_tone, _stage_to_legacy_intent, route,
    classify_intent,  # 保留的旧函数，验证不报错
)


class TestClassifyStage(unittest.TestCase):
    """6 阶段交互识别"""

    # ── correct（纠偏）──
    def test_correction_simple(self):
        self.assertEqual(classify_stage("\u4e0d\u5bf9", {}), 'correct')

    def test_correction_detailed(self):
        self.assertEqual(classify_stage("\u4e0d\u662f\u8fd9\u4e2a\u610f\u601d", {}), 'correct')

    def test_correction_with_skill(self):
        """纠偏即使有技能关键词也应走 correct"""
        self.assertEqual(
            classify_stage("\u4e0d\u5bf9 \u6211\u6ca1\u8bf4\u67e5\u5929\u6c14",
                          {'matched_skill': 'weather', 'skill_score': 3.0}),
            'correct'
        )

    def test_correction_understanding(self):
        self.assertEqual(classify_stage("\u4f60\u7406\u89e3\u9519\u4e86", {}), 'correct')

    def test_correction_didnt_say(self):
        self.assertEqual(classify_stage("\u6211\u6ca1\u8bf4\u8fd9\u4e2a", {}), 'correct')

    # ── confirm（确认执行）──
    def test_confirm_start(self):
        self.assertEqual(classify_stage("\u5f00\u59cb\u5427", {}), 'confirm')

    def test_confirm_this_one(self):
        self.assertEqual(classify_stage("\u90a3\u5c31\u8fd9\u4e2a", {}), 'confirm')

    def test_confirm_go_ahead(self):
        self.assertEqual(classify_stage("\u5c31\u6309\u4f60\u8bf4\u7684", {}), 'confirm')

    def test_confirm_with_task_and_skill_becomes_request(self):
        """确认词 + 任务词 + 技能关键词 → 应该走 request（'好的帮我查天气'）"""
        self.assertEqual(
            classify_stage("\u597d\u7684\u5e2e\u6211\u67e5\u5929\u6c14",
                          {'matched_skill': 'weather', 'skill_score': 3.0}),
            'request'
        )

    # ── inform（自述）──
    def test_inform_location(self):
        self.assertEqual(classify_stage("\u6211\u5728\u5e38\u5dde", {}), 'inform')

    def test_inform_name(self):
        self.assertEqual(classify_stage("\u6211\u53eb\u5f6c\u54e5", {}), 'inform')

    def test_inform_with_task_becomes_request(self):
        """自述 + 任务词 → 不是纯 inform"""
        # "我在常州 帮我查天气" 应该被复合句处理，这里测单句
        stage = classify_stage("\u6211\u5728\u5e38\u5dde\u5e2e\u6211\u67e5",
                              {'matched_skill': 'weather', 'skill_score': 3.0})
        self.assertNotEqual(stage, 'inform')

    # ── explore（探索/讨论）──
    def test_explore_hypothetical(self):
        self.assertEqual(classify_stage("\u5982\u679c\u8981\u753b\u6d77\u62a5\u7684\u8bdd", {}), 'explore')

    def test_explore_suggestion(self):
        self.assertEqual(classify_stage("\u4f60\u89c9\u5f97\u8fd9\u4e2a\u65b9\u6848\u600e\u4e48\u6837", {}), 'explore')

    def test_explore_or(self):
        self.assertEqual(classify_stage("\u6216\u8005\u73a9\u6e38\u620f\u90fd\u53ef\u4ee5", {}), 'explore')

    def test_explore_brainstorm(self):
        self.assertEqual(classify_stage("\u5934\u8111\u98ce\u66b4\u5427 \u6216\u8005\u73a9\u6e38\u620f\u90fd\u53ef\u4ee5", {}), 'explore')

    def test_explore_with_task_and_skill_becomes_request(self):
        """探索词 + 任务词 + 技能关键词 → request（'能不能帮我查天气'）"""
        self.assertEqual(
            classify_stage("\u80fd\u4e0d\u80fd\u5e2e\u6211\u67e5\u5929\u6c14",
                          {'matched_skill': 'weather', 'skill_score': 3.0}),
            'request'
        )

    # ── request（明确请求）──
    def test_request_weather(self):
        self.assertEqual(
            classify_stage("\u5e2e\u6211\u67e5\u5929\u6c14",
                          {'matched_skill': 'weather', 'skill_score': 3.0}),
            'request'
        )

    def test_request_draw(self):
        self.assertEqual(
            classify_stage("\u5e2e\u6211\u753b\u4e2a\u6d77\u62a5",
                          {'matched_skill': 'draw', 'skill_score': 3.0}),
            'request'
        )

    def test_request_article(self):
        self.assertEqual(
            classify_stage("\u5199\u7bc7\u6587\u7ae0",
                          {'matched_skill': 'article', 'skill_score': 3.0}),
            'request'
        )

    def test_request_multi_keyword(self):
        """多关键词命中 → evidence 至少 2 → request"""
        self.assertEqual(
            classify_stage("\u5e38\u5dde\u5929\u6c14\u600e\u4e48\u6837",
                          {'matched_skill': 'weather', 'skill_score': 2.0}),
            'request'
        )

    # ── social（闲聊）──
    def test_social_greeting(self):
        self.assertEqual(classify_stage("\u4f60\u597d", {}), 'social')

    def test_social_laugh(self):
        self.assertEqual(classify_stage("\u54c8\u54c8", {}), 'social')

    def test_social_tired(self):
        self.assertEqual(classify_stage("\u597d\u7d2f", {}), 'social')

    def test_social_empty(self):
        self.assertEqual(classify_stage("", {}), 'social')

    def test_social_default(self):
        """无特征词 → 默认 social"""
        self.assertEqual(classify_stage("\u4eca\u5929\u5929\u771f\u84dd", {}), 'social')


class TestClassifyTone(unittest.TestCase):
    """7 语气识别"""

    def test_correct_tone(self):
        self.assertEqual(classify_tone("\u4e0d\u5bf9"), 'correct')

    def test_complaint_tone(self):
        self.assertEqual(classify_tone("\u53c8\u6765\u4e86 \u70e6\u6b7b\u4e86"), 'complaint')

    def test_hypothetical_tone(self):
        self.assertEqual(classify_tone("\u5982\u679c\u660e\u5929\u4e0b\u96e8"), 'hypothetical')

    def test_command_tone(self):
        self.assertEqual(classify_tone("\u5e2e\u6211\u67e5\u4e00\u4e0b"), 'command')

    def test_request_tone(self):
        self.assertEqual(classify_tone("\u80fd\u4e0d\u80fd\u5e2e\u6211\u770b\u770b"), 'request')

    def test_suggest_tone(self):
        self.assertEqual(classify_tone("\u6216\u8005\u8bd5\u8bd5\u770b"), 'suggest')

    def test_discuss_tone(self):
        self.assertEqual(classify_tone("\u4f60\u89c9\u5f97\u5462"), 'discuss')

    def test_default_tone(self):
        self.assertEqual(classify_tone("\u4eca\u5929\u5929\u771f\u84dd"), 'discuss')


class TestStageLegacyMapping(unittest.TestCase):
    """阶段 → 旧 intent 映射"""

    def test_correct_maps_to_chat(self):
        self.assertEqual(_stage_to_legacy_intent('correct'), 'chat')

    def test_confirm_maps_to_task(self):
        self.assertEqual(_stage_to_legacy_intent('confirm'), 'task')

    def test_social_maps_to_chat(self):
        self.assertEqual(_stage_to_legacy_intent('social'), 'chat')

    def test_explore_maps_to_discuss(self):
        self.assertEqual(_stage_to_legacy_intent('explore'), 'discuss')

    def test_inform_maps_to_inform(self):
        self.assertEqual(_stage_to_legacy_intent('inform'), 'inform')

    def test_request_maps_to_task(self):
        self.assertEqual(_stage_to_legacy_intent('request'), 'task')


class TestRouteBackwardCompat(unittest.TestCase):
    """验证 route() 输出向后兼容"""

    LEGACY_FIELDS = ('mode', 'skill', 'confidence', 'reason', 'params',
                     'role', 'chat_score', 'skill_score', 'emotion_score')
    NEW_FIELDS = ('stage', 'tone')

    def test_route_has_legacy_fields(self):
        result = route("\u4f60\u597d")
        for field in self.LEGACY_FIELDS:
            self.assertIn(field, result, f"\u7f3a\u5c11\u65e7\u5b57\u6bb5: {field}")

    def test_route_has_new_fields(self):
        result = route("\u4f60\u597d")
        for field in self.NEW_FIELDS:
            self.assertIn(field, result, f"\u7f3a\u5c11\u65b0\u5b57\u6bb5: {field}")

    def test_greeting_is_chat_mode(self):
        result = route("\u4f60\u597d")
        self.assertEqual(result['mode'], 'chat')
        self.assertEqual(result['stage'], 'social')

    def test_correction_has_correct_stage(self):
        result = route("\u4e0d\u5bf9 \u4e0d\u662f\u8fd9\u4e2a\u610f\u601d")
        self.assertEqual(result['mode'], 'chat')
        self.assertEqual(result['stage'], 'correct')
        self.assertEqual(result['skill_score'], 0.0)

    def test_hypothetical_is_explore(self):
        result = route("\u5982\u679c\u8981\u753b\u6d77\u62a5\u7684\u8bdd")
        self.assertEqual(result['mode'], 'chat')
        self.assertEqual(result['stage'], 'explore')
        self.assertEqual(result['tone'], 'hypothetical')

    def test_inform_is_chat(self):
        result = route("\u6211\u5728\u5e38\u5dde")
        self.assertEqual(result['mode'], 'chat')
        self.assertEqual(result['stage'], 'inform')

    def test_answer_correction_intent_preserved(self):
        """特殊检测器的 intent 值必须保留"""
        result = route("\u4e0d\u662f\u8fd9\u4e2a \u6211\u8bf4\u7684\u4e0d\u662f\u8fd9\u4e2a \u4f60\u53d1\u5929\u6c14\u4e4b\u524d")
        self.assertEqual(result.get('intent'), 'answer_correction')
        self.assertEqual(result['stage'], 'correct')

    def test_meta_bug_report_intent_preserved(self):
        result = route("\u4ee3\u7801\u5c0f\u6e38\u620f\u7684\u7a97\u53e3\u53c8\u8df3\u51fa\u6765\u4e86 \u8def\u5f84\u6709\u95ee\u9898")
        self.assertEqual(result.get('intent'), 'meta_bug_report')
        self.assertEqual(result['stage'], 'correct')
        self.assertEqual(result['tone'], 'complaint')

    def test_ability_query_intent_preserved(self):
        result = route("\u4f60\u4f1a\u4ec0\u4e48")
        self.assertEqual(result.get('intent'), 'ability_capability')
        self.assertEqual(result['stage'], 'social')


class TestClassifyIntentStillWorks(unittest.TestCase):
    """旧的 classify_intent 保留不删，验证能正常调用"""

    def test_old_classify_intent_runs(self):
        result = classify_intent("\u4f60\u597d", {})
        self.assertIn(result, ('task', 'discuss', 'inform', 'chat'))

    def test_old_classify_intent_discuss(self):
        result = classify_intent("\u5982\u679c\u8981\u753b\u6d77\u62a5", {'matched_skill': 'draw'})
        self.assertEqual(result, 'discuss')


if __name__ == '__main__':
    unittest.main()
