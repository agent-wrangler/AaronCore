# 简单日志系统
import os
import json
from datetime import datetime

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")

def ensure_log_dir():
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)

def log_brain(user_input, role, skill_used, result, response_length):
    """记录大脑活动"""
    ensure_log_dir()
    
    log_file = os.path.join(LOG_DIR, "brain.log")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    entry = {
        "time": timestamp,
        "user_input": user_input[:50],
        "role": role,
        "skill": skill_used,
        "result_len": response_length
    }
    
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def log_event(event_type, data):
    """记录事件"""
    ensure_log_dir()
    
    log_file = os.path.join(LOG_DIR, "events.log")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    entry = {
        "time": timestamp,
        "event": event_type,
        "data": str(data)[:100]
    }
    
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def log_error(error_type, message):
    """记录错误"""
    ensure_log_dir()
    
    log_file = os.path.join(LOG_DIR, "errors.log")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    entry = {
        "time": timestamp,
        "error_type": error_type,
        "message": message[:200]
    }
    
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

print("[Logs] Log system initialized")
