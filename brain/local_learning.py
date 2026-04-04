import json
import os
import re


_PERSONA_FILE = ""
_sync_name_in_persona = None


def configure(persona_file: str, sync_name_in_persona_fn):
    global _PERSONA_FILE, _sync_name_in_persona
    _PERSONA_FILE = str(persona_file or "")
    _sync_name_in_persona = sync_name_in_persona_fn


def auto_learn(user_input: str, ai_response: str = "") -> str:
    nova_rename_patterns = [
        r"你以后叫(.+)",
        r"你改名叫(.+)",
        r"你叫(.+)吧",
        r"以后你叫(.+)",
    ]
    nova_rename_ask_patterns = [
        r"想给你改个名字",
        r"给你起个名字",
    ]

    for pattern in nova_rename_patterns:
        match = re.search(pattern, user_input)
        if match:
            new_name = match.group(1).strip().rstrip("吧啊呀嘛")
            if new_name and len(new_name) <= 20:
                config_path = str(_PERSONA_FILE)
                try:
                    persona = {}
                    if os.path.exists(config_path):
                        with open(config_path, "r", encoding="utf-8") as handle:
                            persona = json.load(handle)
                    persona["nova_name"] = new_name
                    if _sync_name_in_persona:
                        _sync_name_in_persona(persona, new_name)
                    with open(config_path, "w", encoding="utf-8") as handle:
                        json.dump(persona, handle, ensure_ascii=False, indent=2)
                except Exception:
                    pass
                return f"好呀！以后叫我{new_name}就行啦～"

    for pattern in nova_rename_ask_patterns:
        if re.search(pattern, user_input):
            return "好呀，你想叫我什么？直接说就行～"

    select_patterns = [r"^1$", r"^2$", r"^3$", r"^(小可爱|Nova酱|阿Nova|甜心|小\s*Nova)$"]
    for pattern in select_patterns:
        match = re.search(pattern, user_input.strip())
        if match:
            config_path = str(_PERSONA_FILE)
            if os.path.exists(config_path):
                try:
                    with open(config_path, "r", encoding="utf-8") as handle:
                        persona = json.load(handle)
                    if persona.get("waiting_name"):
                        new_name = user_input.strip()
                        if new_name == "1":
                            new_name = persona["waiting_name"][0]
                        elif new_name == "2":
                            new_name = persona["waiting_name"][1]
                        elif new_name == "3":
                            new_name = persona["waiting_name"][2]
                        persona["nova_name"] = new_name
                        del persona["waiting_name"]
                        if _sync_name_in_persona:
                            _sync_name_in_persona(persona, new_name)
                        with open(config_path, "w", encoding="utf-8") as handle:
                            json.dump(persona, handle, ensure_ascii=False, indent=2)
                        return f"好呀好呀～以后人家就叫{new_name}啦！"
                except Exception:
                    pass

    call_patterns = [
        r"叫我(.+)",
        r"以后叫我(.+)",
        r"叫我(.+)吧",
        r"以后叫我(.+)啊",
    ]

    for pattern in call_patterns:
        match = re.search(pattern, user_input)
        if match:
            new_name = match.group(1)
            from memory import update_persona

            update_persona("user", new_name)
            return f"好哒！以后就叫你{new_name}啦～"

    remember_patterns = [
        r"记住(.+)",
        r"要记住(.+)",
        r"别忘了(.+)",
        r"把我(.+)记住",
    ]

    for pattern in remember_patterns:
        match = re.search(pattern, user_input)
        if match:
            content = match.group(1)
            from memory import add_long_term

            add_long_term(content, "event")
            return f"记住啦！{content}～"

    try:
        from memory import evolve

        evolve(user_input, ai_response or "")
    except Exception:
        pass

    return ""
