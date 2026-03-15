# NovaCore 配置中心
# 统一管理当前仓库内的相对路径，避免继续引用旧环境。

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ==================== 路径配置 ====================
PATH = {
    "root": str(ROOT),
    "memory_db": str(ROOT / "memory_db"),
    "logs": str(ROOT / "logs"),
    "skills": str(ROOT / "core" / "skills"),
}

# ==================== 模型配置 ====================
MODEL = {
    "default": "minimax-m2.5",
    "temperature": 0.7,
    "max_tokens": 2000,
}

# ==================== 记忆配置 ====================
MEMORY = {
    "l3_max": 20,        # L3长期记忆上限
    "l4_trigger": 1,     # L4人格更新阈值
    "cache_ttl": 86400,  # 缓存过期时间(秒)=3天
}

# ==================== 技能配置 ====================
SKILLS = {
    "auto_load": True,       # 自动加载技能
    "learn_threshold": 3,   # 自动学习阈值
    "timeout": 30,          # 技能执行超时(秒)
}

# ==================== 进化配置 ====================
EVOLUTION = {
    "auto_trigger": 0.1,    # L8自动触发概率10%
    "periodic_runs": 50,    # 周期复盘间隔
}

# ==================== 日志配置 ====================
LOG = {
    "level": "info",         # debug/info/warning/error
    "brain_log": True,      # 记录大脑活动
    "event_log": True,      # 记录事件
    "error_log": True,      # 记录错误
}

# ==================== API配置 ====================
API = {
    "host": "0.0.0.0",
    "port": 8090,
    "title": "NovaCore",
    "version": "4.0",
}

# ==================== 关系模式 ====================
ROLE_KEYWORDS = {
    "friend": ["累", "烦", "心情", "难过", "开心", "想聊", "陪我", "郁闷", "压力"],
    "executor": ["规划", "做一个", "帮我完成", "项目", "系统", "设计", "开发"],
}

# 获取配置
def get(key):
    """获取配置"""
    for section in [PATH, MODEL, MEMORY, SKILLS, EVOLUTION, LOG, API]:
        if key in section:
            return section[key]
    return None
