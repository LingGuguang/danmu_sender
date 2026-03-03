"""
纯文本到 emoji 的映射：输入 [跳舞]、[爱心] 等会被替换为对应 emoji 后发送。
映射表可按需扩展。
"""
import re
from typing import Dict, List, Tuple

# [关键词] -> emoji（按关键词长度从长到短排序，避免 [笑哭] 被拆成 [笑]+[哭]）
TEXT_TO_EMOJI: Dict[str, str] = {
    # 表情类（长的先写）
    "[捂脸哭]": "😭",
    "[翻白眼]": "🙄",
    "[打call]": "🤳",
    "[狗头]": "🐕",
    "[滑稽]": "😏",
    "[抠鼻]": "🤏",
    "[吐舌]": "😛",
    "[捂脸]": "🤦",
    "[笑哭]": "😂",
    "[心碎]": "💔",
    "[得意]": "😎",
    "[惊讶]": "😲",
    "[无语]": "😑",
    "[害羞]": "😊",
    "[呲牙]": "😁",
    "[抱拳]": "🙏",
    "[吃瓜]": "🍉",
    "[跳舞]": "💃",
    "[点赞]": "👍",
    "[鼓掌]": "👏",
    "[抱抱]": "🤗",
    "[笑]": "😄",
    "[哭]": "😢",
    "[生气]": "😠",
    "[喜欢]": "😍",
    "[吐]": "🤮",
    "[呆]": "😶",
    "[酷]": "😎",
    "[爱心]": "❤️",
    "[耶]": "✌️",
    "[OK]": "👌",
    "[加油]": "💪",
    # 物品/符号
    "[玫瑰]": "🌹",
    "[礼物]": "🎁",
    "[蛋糕]": "🎂",
    "[啤酒]": "🍺",
    "[干杯]": "🥂",
    "[火]": "🔥",
    "[星星]": "⭐",
    "[太阳]": "☀️",
    "[月亮]": "🌙",
    "[晚安]": "🌙",
    "[666]": "🔥",
}


# 匹配仍留在文本中的 [xxx]，用于检测未识别的关键词
_BRACKET_PATTERN = re.compile(r"\[[^\]]+\]")


def replace_text_emoji(text: str) -> str:
    """
    将文本中的 [关键词] 替换为对应 emoji。
    按关键词长度从长到短替换，避免子串被误替换。
    """
    if not text:
        return text
    # 按 key 长度降序，先替换长的
    for key in sorted(TEXT_TO_EMOJI.keys(), key=len, reverse=True):
        text = text.replace(key, TEXT_TO_EMOJI[key])
    return text


def get_unmatched_brackets(text_after_replace: str) -> List[str]:
    """返回替换后文本中仍存在的 [xxx]，即无法匹配到 emoji 的关键词（去重）。"""
    if not text_after_replace:
        return []
    found = _BRACKET_PATTERN.findall(text_after_replace)
    return list(dict.fromkeys(found))


def get_available_emoji_keys() -> List[str]:
    """返回所有可用的 [关键词] 列表，按长度降序。"""
    return sorted(TEXT_TO_EMOJI.keys(), key=len, reverse=True)


def get_emoji_help_lines() -> list[str]:
    """返回简短提示，列出部分常用映射供用户参考。"""
    examples = ["[跳舞]", "[爱心]", "[笑]", "[哭]", "[666]", "[狗头]", "[点赞]"]
    return [
        "支持输入 [关键词] 自动转 emoji，例如: " + " ".join(examples) + " （输入 help-emoji 可看全部）",
    ]
