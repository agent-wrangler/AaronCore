# 讲故事技能
import json
import random
import re
from datetime import datetime
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
HISTORY_PATH = ROOT_DIR / "memory_db" / "msg_history.json"
STORY_STATE_PATH = ROOT_DIR / "memory_db" / "story_state.json"

FOLLOW_UP_HINTS = ("继续讲", "然后呢", "后来呢", "接着讲", "讲长一点", "有点短", "太短")
NEW_STORY_HINTS = ("再讲一个", "换一个故事", "换个故事", "重新讲一个")
LONG_STORY_HINTS = ("长一点", "完整", "详细", "慢慢讲", "多一点", "长篇", "睡前")

CHAPTER_NUMBERS = {
    1: "第一章",
    2: "第二章",
    3: "第三章",
    4: "第四章",
    5: "第五章",
    6: "第六章",
}

THEMES = [
    {
        "id": "forest_fox",
        "keywords": ["狐狸", "森林", "月亮", "萤火虫"],
        "title": ["月灯森林的最后一把钥匙", "小狐狸和会唱歌的月光井"],
        "protagonist": "小狐狸阿雾",
        "setting": "月灯森林",
        "wish": "找到一口会唱歌的月光井，让整片森林重新亮起来",
        "artifact": "一枚会发热的银叶钥匙",
        "obstacle": "一条总在半夜起雾的回声河",
        "helper": "一只总爱绕着他打转的萤火虫小灯",
        "twist": "那口井并不是要被打开，而是要有人愿意把自己的心事轻轻放进去",
        "ending": "森林里的路灯一盏盏亮起，连最胆小的小动物都敢抬头看月亮了",
        "continuations": [
            {
                "hook": "可第二天夜里，银叶钥匙又一次发起烫来，像是在催它回到井边。",
                "challenge": "井底浮上来一圈圈很浅的光纹，每一圈都像在重复森林里那些没说出口的遗憾。",
                "helper": "萤火虫小灯绕着阿雾慢慢飞，把它曾经害怕过的每一个地方都重新照亮了一遍。",
                "reveal": "阿雾终于听清，那些回声其实是森林里每个小动物偷偷藏起来的愿望。",
                "ending": "它把那些愿望一条条记了下来，准备替大家完成井里留下的最后一道委托。",
            },
            {
                "hook": "第三个夜晚来临时，整片森林忽然安静得有些反常，连风都像不敢大声经过。",
                "challenge": "阿雾得在月光消失前，把写满愿望的叶片挂回最老的那棵树上，不然井里的光会再次熄掉。",
                "helper": "小灯带着更多萤火虫赶来，像一条发亮的小河，把黑暗的树梢一截截接了起来。",
                "reveal": "阿雾这才明白，真正打开月光井的不是钥匙，而是愿意替别人认真守护心事的那份心。",
                "ending": "等最后一片叶子挂好时，井水里浮出一轮完整的月亮，整座森林都轻轻亮了起来。",
            },
            {
                "hook": "后来很久以后，每逢有谁在夜里难过，月灯森林都会自动亮起一盏小小的路灯。",
                "challenge": "阿雾开始学着守夜，它怕自己一旦睡着，就会错过那些在黑暗里小声求救的声音。",
                "helper": "这一次，不只是小灯，连曾经胆小的小动物们也轮流陪它一起守着那口井。",
                "reveal": "阿雾终于不再把自己当成那个总是害怕的小狐狸，因为它已经变成了别人心里那盏灯。",
                "ending": "从那以后，谁走进月灯森林，都能顺着那一点点柔光回到家。",
            },
        ],
    },
    {
        "id": "clock_robot",
        "keywords": ["机器人", "星星", "宇宙", "天文台"],
        "title": ["旧天文台里的小机器人", "零零和掉下来的那颗纸星星"],
        "protagonist": "小机器人零零",
        "setting": "海边山坡上的旧天文台",
        "wish": "修好那台停了很多年的星图机，替大家重新找到夜空的方向",
        "artifact": "一枚刻着星轨的黄铜齿轮",
        "obstacle": "每到深夜就会把整座山包裹住的雾风暴",
        "helper": "一只总把信纸叼来叼去的纸星鸟",
        "twist": "零零以为缺的是齿轮，最后才发现星图机真正缺的是有人相信它还值得再次启动",
        "ending": "天文台重新亮起温暖的橘色灯，山下的孩子们又能在屋顶上认出自己的星座",
        "continuations": [
            {
                "hook": "可在星图机恢复转动后的第二晚，山下却有人发现一整片熟悉的星座忽然从夜空里消失了。",
                "challenge": "零零不得不带着纸星鸟沿着旧信号塔一路往海边跑，想找出是哪一段星轨断掉了。",
                "helper": "纸星鸟把一封封多年没送出的信从风里叼回来，每一封都写着曾经看过那片星空的人留下的愿望。",
                "reveal": "零零慢慢明白，星图机连接的不只是夜空，还有那些一直相信它的人。",
                "ending": "它把那些信一封封塞进星图机侧面的旧抽屉里，机器的光立刻又稳了下来。",
            },
            {
                "hook": "第三个夜里，海上的雾风暴卷得比以前更高，像是整片夜空都快要被擦掉了。",
                "challenge": "零零必须在天亮前爬上最高的圆顶，把最后一枚备用齿轮送进停转的主轴里。",
                "helper": "山下的孩子们一盏一盏地点亮手电，替它把上山的路照得像一条发光的阶梯。",
                "reveal": "零零终于知道，原来自己一直寻找的回家路，就藏在这些一起抬头看星星的人中间。",
                "ending": "等齿轮咬合的那一刻，整片夜空重新转动起来，连最远那颗星也慢慢亮了。",
            },
            {
                "hook": "后来天文台成了很多孩子的秘密基地，大家总爱在傍晚跑来听零零讲星座背后的故事。",
                "challenge": "零零偶尔还是会担心，万一哪一天机器再次停下，大家会不会很失望。",
                "helper": "可每当它这么想，纸星鸟就会把新的小纸条轻轻放到它掌心里，上面全是谢谢和喜欢。",
                "reveal": "它这才明白，自己真正修好的从来不只是一台机器，还有很多人愿意再次相信夜晚的心。",
                "ending": "于是旧天文台的灯一直亮着，成了海边每一个归家的人都看得见的小星星。",
            },
        ],
    },
    {
        "id": "seaside_cat",
        "keywords": ["猫", "小猫", "面包", "海边", "小镇"],
        "title": ["海风面包店的小猫", "会做梦香味的小猫云朵"],
        "protagonist": "小猫云朵",
        "setting": "有海风和钟声的白石小镇",
        "wish": "在黎明前做出一炉能安慰失眠人的好梦面包",
        "artifact": "一本边角都卷起来的旧食谱",
        "obstacle": "怎么也揉不出温度的夜面团",
        "helper": "住在钟楼里的老燕子阿针",
        "twist": "食谱上最重要的一味材料并不是糖和牛奶，而是把想说却没说出口的话轻轻写下来",
        "ending": "天亮时，整条街都飘着暖暖的麦香，连总皱着眉的人也会慢下来笑一下",
        "continuations": [
            {
                "hook": "可第二天深夜，面包店门缝底下又被人塞进来一张皱巴巴的小纸条。",
                "challenge": "纸条上没有名字，只写着一句“我还是睡不着”，让云朵怎么也放心不下。",
                "helper": "老燕子阿针从钟楼飞下来，带着它一户一户地找，想看看是谁把心事藏得这么紧。",
                "reveal": "云朵最后发现，那个人需要的并不只是面包，而是有人愿意坐下来陪他把话慢慢说完。",
                "ending": "于是那一夜，面包店亮到很晚，窗边却多了一个终于肯松口气的笑脸。",
            },
            {
                "hook": "第三个凌晨，海风忽然变咸了许多，连发酵箱里的面团都像跟着低落起来。",
                "challenge": "云朵得赶在钟声敲响前，把每一张写满心事的小纸条都折进新的面包里。",
                "helper": "整条街的邻居都悄悄帮忙，有人揉面，有人看火，还有人替它把窗户边的小灯重新擦亮。",
                "reveal": "云朵第一次明白，原来一座小镇的温柔，是可以一起被烤出来的。",
                "ending": "天亮时，那炉面包的香气一路飘到码头边，连最早出海的人都停下来深深吸了一口气。",
            },
            {
                "hook": "后来很多人开始把难过写成小纸条塞进面包店门口的木盒里。",
                "challenge": "云朵怕自己有一天忙不过来，照顾不到每一份小小的难过。",
                "helper": "可阿针笑它想太多，因为现在会帮忙的人已经从一只燕子变成了一整条街。",
                "reveal": "云朵这才发现，自己做出来的不是普通面包，而是一种能让人重新想好好过日子的香味。",
                "ending": "白石小镇从那以后总带着暖烘烘的甜香，像把整个清晨都提前揉进了日子里。",
            },
        ],
    },
    {
        "id": "lake_whale",
        "keywords": ["鲸鱼", "湖", "梦", "夜晚", "治愈"],
        "title": ["星湖里睡不着的小鲸鱼", "小鲸鱼和夜里发光的水纹"],
        "protagonist": "小鲸鱼蓝葡萄",
        "setting": "会映出整片银河的玻璃星湖",
        "wish": "学会在夜里唱出一首能让自己安心睡着的歌",
        "artifact": "一片会在水里发出微光的贝壳",
        "obstacle": "每当它快闭上眼时就会被自己心里的回声吵醒",
        "helper": "一位总是慢慢说话的乌龟邮差",
        "twist": "蓝葡萄寻找的并不是让世界安静下来，而是学会在自己的心跳里找到节奏",
        "ending": "后来每到夜里，整片星湖都会随着它的歌声轻轻起伏，像一张很软很软的被子",
        "continuations": [
            {
                "hook": "可第二晚，湖面上又漂来一圈陌生的发光水纹，像是别人的梦悄悄迷了路。",
                "challenge": "蓝葡萄必须顺着那串微光游到湖心，把那枚贝壳轻轻按进最亮的波纹里。",
                "helper": "乌龟邮差慢吞吞地跟在旁边，一边划水一边提醒它，不要急，梦这种东西要慢慢哄。",
                "reveal": "蓝葡萄后来才知道，原来那不是别人的梦，而是自己很久以前没来得及安放好的害怕。",
                "ending": "当它愿意回头抱一抱那份害怕时，湖心的水终于柔软了下来。",
            },
            {
                "hook": "第三个夜里，玻璃星湖下起了很轻的流星雨，像有人把整片银河揉碎撒进了水里。",
                "challenge": "蓝葡萄一边想睡，一边又怕一闭眼就错过那些落进湖底的小亮点。",
                "helper": "乌龟邮差把背上的旧信包打开，里面全是以前别人写给夜晚的愿望，慢慢念给它听。",
                "reveal": "蓝葡萄终于明白，睡着不是失去世界，而是把自己轻轻交给世界一会儿。",
                "ending": "那一夜，它第一次在自己的歌声里慢慢睡着了，连尾鳍都带着很安稳的弧度。",
            },
            {
                "hook": "后来每当有谁在夜里睡不着，星湖边总会传来一小段很轻很轻的哼唱。",
                "challenge": "蓝葡萄偶尔还是会想起从前那个总被回声吵醒的自己，心口会轻轻紧一下。",
                "helper": "可湖边的小鱼、小鸟，还有乌龟邮差都会不紧不慢地陪着它，直到它重新放松下来。",
                "reveal": "它终于学会了，原来安稳不是永远不害怕，而是害怕的时候也知道自己有人陪。",
                "ending": "所以整片星湖后来都睡得很好，夜晚也变得像一封慢慢展开的温柔长信。",
            },
        ],
    },
]


def _load_recent_messages(limit: int = 16):
    try:
        if HISTORY_PATH.exists():
            data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data[-limit:]
    except Exception:
        pass
    return []


def _load_story_state() -> dict:
    try:
        if STORY_STATE_PATH.exists():
            data = json.loads(STORY_STATE_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def _save_story_state(state: dict):
    STORY_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STORY_STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _history_text(limit: int = 16) -> str:
    parts = []
    for item in _load_recent_messages(limit):
        content = str(item.get("content") or "").strip()
        if content:
            parts.append(content)
    return "\n".join(parts)


def _find_theme_by_id(theme_id: str):
    for theme in THEMES:
        if theme["id"] == theme_id:
            return theme
    return None


def _detect_theme(text: str):
    lowered = str(text or "").lower()
    for theme in THEMES:
        for keyword in theme["keywords"]:
            if keyword.lower() in lowered:
                return theme
    return None


def _extract_story_title(text: str) -> str:
    match = re.search(r"《([^》]+)》", str(text or ""))
    if not match:
        return ""
    title = match.group(1).strip()
    return title.split("·第", 1)[0].strip()


def _restore_story_state_from_history() -> dict:
    for item in reversed(_load_recent_messages(20)):
        if str(item.get("role")) not in ("nova", "assistant"):
            continue
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        title = _extract_story_title(content)
        theme = _detect_theme(content)
        if title and theme:
            return {
                "theme_id": theme["id"],
                "title": title,
                "chapter": 1,
                "last_query": "",
                "updated_at": datetime.now().isoformat(),
            }
    return {}


def _current_story_state() -> dict:
    state = _load_story_state()
    if state:
        return state
    restored = _restore_story_state_from_history()
    if restored:
        _save_story_state(restored)
    return restored


def _pick_theme(query: str, state: dict):
    query = str(query or "").strip()
    history_text = _history_text()
    requested_theme = _detect_theme(query)
    previous_theme = _find_theme_by_id(state.get("theme_id", "")) if state else None
    if previous_theme is None:
        previous_theme = _detect_theme(history_text)

    if requested_theme:
        return requested_theme

    if any(word in query for word in NEW_STORY_HINTS) and previous_theme:
        other_themes = [theme for theme in THEMES if theme["id"] != previous_theme["id"]]
        if other_themes:
            return random.choice(other_themes)

    if previous_theme and "故事" in query and not any(word in query for word in NEW_STORY_HINTS):
        return previous_theme

    return random.choice(THEMES)


def _paragraph_target(query: str, continuation: bool = False) -> int:
    text = str(query or "").strip()
    count = 5 if not continuation else 6
    if any(word in text for word in LONG_STORY_HINTS):
        count += 1
    if any(word in text for word in FOLLOW_UP_HINTS):
        count += 1
    if "睡前" in text or "治愈" in text or "温柔" in text:
        count += 1
    return min(count, 8 if continuation else 7)


def _opening_paragraph(theme: dict) -> str:
    templates = [
        (
            f"在{theme['setting']}里，{theme['protagonist']}一直想{theme['wish']}。"
            f"它并不是天生勇敢的那一种，很多时候只是把耳朵竖起来，假装自己一点也不害怕。"
            "可每当夜色慢慢落下来，它还是会忍不住朝最安静的那条小路望过去。"
        ),
        (
            f"{theme['setting']}一到晚上就会变得特别安静，只有风吹过时会带起一点点发亮的尘屑。"
            f"{theme['protagonist']}住在那里已经很久了，可心里一直藏着同一个愿望：{theme['wish']}。"
        ),
    ]
    return random.choice(templates)


def _story_segments(theme: dict):
    return [
        (
            f"那天夜里，{theme['protagonist']}在门口捡到了{theme['artifact']}。"
            f"它刚把那东西捧起来，前方就传来一阵很轻很轻的回响，像是谁在远处喊它的名字。"
            f"它知道，声音一定是从{theme['obstacle']}那边传来的。"
        ),
        (
            f"可要靠近那里一点都不容易。{theme['obstacle']}白天看起来只是普通的一段路，"
            "到了晚上却总会把方向悄悄藏起来。走着走着，连脚边的石子都像在故意捉弄人，"
            "往前一步像对，退后一步又像更对。"
        ),
        (
            f"就在{theme['protagonist']}差点想转身回去的时候，{theme['helper']}出现了。"
            "它没有说很多大道理，只是陪在旁边，一会儿往左晃一晃，一会儿往前亮一亮，"
            "像是在告诉它，有些路并不是因为不怕才敢走，而是因为想守住心里的东西，才愿意继续往前。"
        ),
        (
            f"再往深处走，{theme['protagonist']}才发现自己一直误会了一件事：{theme['twist']}。"
            "它站在原地愣了好一会儿，忽然觉得胸口那些慌乱的情绪慢慢散开了。"
            "原来很多看上去像考验的东西，不过是在等一个人终于愿意认真听听自己的心。"
        ),
        (
            f"于是，{theme['protagonist']}照着心里最柔软的那个念头去做了。"
            "它没有再急着证明自己，也没有拼命和夜色较劲，只是很安静地把想说的话、"
            "想守住的人、还有一路上的害怕都放进了眼前那团微光里。"
        ),
        (
            f"下一秒，周围的空气像被人轻轻拨了一下，整条路都亮了起来。{theme['ending']}。"
            f"{theme['protagonist']}这才明白，真正让世界变亮的，从来不只是奇迹本身，"
            "还有它终于愿意迈出去的那一步。"
        ),
    ]


def _ending_paragraph(theme: dict, extra_soft: bool) -> str:
    if extra_soft:
        return (
            f"后来大家再提起那一晚的时候，总会先想起{theme['protagonist']}当时那副认真又有点笨拙的样子。"
            "可也正因为那份认真，很多本来暗下去的东西才重新亮了起来。"
            "从那以后，只要夜风一吹过，大家就知道，原来温柔和勇气真的会悄悄长在同一个人身上。"
        )

    return (
        f"故事的最后，{theme['protagonist']}把{theme['artifact']}收进了自己的小口袋里，"
        "它没有把这场经历挂在嘴边炫耀，只是在后来每一个普通得不能再普通的夜晚里，"
        "都比从前更愿意多走一步、多等一会儿，也多相信一点点好事会发生。"
    )


def _chapter_label(chapter: int) -> str:
    return CHAPTER_NUMBERS.get(chapter, f"第{chapter}章")


def _build_new_story(theme: dict, query: str) -> tuple[str, dict]:
    extra_soft = any(word in query for word in ("睡前", "治愈", "温柔"))
    paragraph_target = _paragraph_target(query, continuation=False)
    title = random.choice(theme["title"])

    paragraphs = [_opening_paragraph(theme)]
    segments = _story_segments(theme)
    paragraphs.extend(segments[: max(paragraph_target - 2, 1)])
    paragraphs.append(_ending_paragraph(theme, extra_soft))

    state = {
        "theme_id": theme["id"],
        "title": title,
        "chapter": 1,
        "last_query": query,
        "updated_at": datetime.now().isoformat(),
    }
    return f"《{title}》\n\n" + "\n\n".join(paragraphs), state


def _continuation_paragraphs(theme: dict, chapter: int, query: str):
    arcs = theme.get("continuations") or []
    arc_index = min(max(chapter - 2, 0), len(arcs) - 1) if arcs else 0
    arc = arcs[arc_index] if arcs else {
        "hook": f"可{theme['protagonist']}后来才发现，事情其实还没有真正结束。",
        "challenge": f"{theme['setting']}里又出现了新的小波动，它得重新回到最开始那条路上。",
        "helper": f"这一次依旧陪着它的，还是{theme['helper']}。",
        "reveal": "它慢慢明白，成长从来不是一晚就完成的事。",
        "ending": "但它已经没那么怕了，因为它知道自己可以再往前一步。",
    }

    paragraphs = [
        (
            f"自从上一章结束以后，{theme['protagonist']}一直以为事情终于可以慢慢安静下来了。"
            f"可{arc['hook']}"
        ),
        arc["challenge"],
        arc["helper"],
        arc["reveal"],
        arc["ending"],
    ]

    if any(word in query for word in LONG_STORY_HINTS + FOLLOW_UP_HINTS) or "睡前" in query:
        paragraphs.insert(
            3,
            (
                f"{theme['protagonist']}这一路走得并不快。它偶尔也会停下来，看看自己影子晃动的方向，"
                "确认那份最初想守住的心意有没有还在。也正是因为这样，它反而比以前更能分清，"
                "哪些声音是真的在呼唤它，哪些只是害怕在吓唬它。"
            ),
        )

    target = _paragraph_target(query, continuation=True)
    return paragraphs[:target]


def _build_continuation_story(theme: dict, state: dict, query: str) -> tuple[str, dict]:
    title = state.get("title") or random.choice(theme["title"])
    chapter = int(state.get("chapter", 1) or 1) + 1
    paragraphs = _continuation_paragraphs(theme, chapter, query)
    state = {
        "theme_id": theme["id"],
        "title": title,
        "chapter": chapter,
        "last_query": query,
        "updated_at": datetime.now().isoformat(),
    }
    return f"《{title}·{_chapter_label(chapter)}》\n\n" + "\n\n".join(paragraphs), state


def execute(topic=""):
    query = str(topic or "").strip()
    state = _current_story_state()
    follow_up = any(word in query for word in FOLLOW_UP_HINTS)
    should_continue = bool(follow_up and state and state.get("theme_id"))

    if should_continue:
        theme = _find_theme_by_id(state.get("theme_id", "")) or _pick_theme(query, state)
        story_text, new_state = _build_continuation_story(theme, state, query)
    else:
        theme = _pick_theme(query, state)
        story_text, new_state = _build_new_story(theme, query)

    _save_story_state(new_state)
    return story_text
