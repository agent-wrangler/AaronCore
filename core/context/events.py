# 事件系统 Event Bus
# 让系统自动触发行为

class EventBus:
    def __init__(self):
        self.handlers = {}
    
    def on(self, event, handler):
        """注册事件处理器"""
        self.handlers.setdefault(event, []).append(handler)
    
    def emit(self, event, data=None):
        """触发事件"""
        for handler in self.handlers.get(event, []):
            try:
                handler(data)
            except Exception as e:
                print(f"[Event] Handler error: {e}")

# 全局事件总线
event_bus = EventBus()

# 常用事件
EVENT_SKILL_FAIL = "skill_fail"
EVENT_SKILL_MISSING = "skill_missing"
EVENT_TASK_COMPLETE = "task_complete"
EVENT_LEARN_NEW = "learn_new"
