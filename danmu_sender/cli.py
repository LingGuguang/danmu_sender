"""终端交互：展示关注直播列表、选择直播间、输入并发送弹幕。"""
from __future__ import annotations

import os
import shutil
import sys
from typing import Any

from .bilibili_api import get_following_live_list, send_danmu
from .cookie_loader import get_last_chrome_failure, load_cookie
from .emoji_map import (
    TEXT_TO_EMOJI,
    get_available_emoji_keys,
    get_unmatched_brackets,
    replace_text_emoji,
)
from .logging_config import get_logger, setup_logging

MAX_MSG_LEN = 30
logger = get_logger("cli")

_RESET = "\033[0m"


def _supports_color() -> bool:
    if not sys.stdout.isatty():
        return False
    if os.environ.get("NO_COLOR") is not None:
        return False
    return os.environ.get("TERM", "").lower() != "dumb"


def _style(text: str, *, color: int | None = None, bold: bool = False, dim: bool = False) -> str:
    if not _supports_color():
        return text
    codes: list[str] = []
    if bold:
        codes.append("1")
    if dim:
        codes.append("2")
    if color is not None:
        codes.append(str(color))
    if not codes:
        return text
    return f"\033[{';'.join(codes)}m{text}{_RESET}"


def _width() -> int:
    size = shutil.get_terminal_size((96, 24)).columns
    return max(72, min(size, 120))


def _cut(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def _print_title(title: str, subtitle: str) -> None:
    line = "═" * min(36, _width() - 2)
    print(_style(f"\n{line}", color=36, bold=True))
    print(_style(title, color=36, bold=True))
    print(_style(subtitle, color=37, dim=True))
    print(_style(f"{line}\n", color=36, bold=True))


def _print_panel(title: str, lines: list[str], *, color: int = 36) -> None:
    w = _width()
    inner = max(36, w - 4)
    head = f" {title} "
    top = "┌" + "─" * inner + "┐"
    bot = "└" + "─" * inner + "┘"
    print(_style(top, color=color))
    print(_style("│" + _cut(head, inner).ljust(inner) + "│", color=color, bold=True))
    for raw in lines:
        print("│" + _cut(raw, inner).ljust(inner) + "│")
    print(_style(bot, color=color))


def _prompt_input(prompt: str) -> str:
    print(prompt)
    return input(_style("› ", color=33, bold=True)).strip()


def _render_live_list(lives: list[dict[str, Any]]) -> None:
    lines: list[str] = []
    for i, item in enumerate(lives, 1):
        title = _cut(item.get("title") or "无标题", 34)
        uname = _cut(item.get("uname") or "未知主播", 16)
        room_id = str(item.get("room_id") or "-")
        lines.append(f"{i:>2}. {uname:<16} | {title:<34} | 房间 {room_id}")
    _print_panel("关注中正在直播", lines, color=36)


def _show_emoji_quick_hint() -> None:
    quick = [
        ("[跳舞]", "💃"),
        ("[爱心]", "❤️"),
        ("[笑]", "😄"),
        ("[哭]", "😢"),
        ("[666]", "🔥"),
        ("[狗头]", "🐕"),
        ("[点赞]", "👍"),
        ("[鼓掌]", "👏"),
    ]
    lines = ["  ".join([f"{k} {v}" for k, v in quick])]
    lines.append("输入 help-emoji 查看全部映射")
    _print_panel("表情包快捷输入", lines, color=35)


def _print_cookie_help(err_msg: str) -> None:
    print(_style(f"获取直播列表失败: {err_msg}", color=31, bold=True))
    if "未登录" not in err_msg and "4100000" not in err_msg:
        return
    print()
    print("【说明】您在浏览器里打开 bilibili.com 是登录状态，但本程序当前拿到的 Cookie 是匿名或无效的。")
    chrome_reason = get_last_chrome_failure()
    if chrome_reason:
        print(f"  从 Chrome 读取 Cookie 失败原因: {chrome_reason}")
    print("  常见原因: Chrome 正在运行时无法读取其 Cookie 数据库（被占用）。")
    print("  请任选其一：")
    print("    1) 关闭 Chrome 后重新运行本程序（程序会从 Chrome 读取登录态）；")
    print("    2) 在 bilibili.com 页面按 F12 → 应用/Application → Cookie → 选中 https://www.bilibili.com，")
    print("       复制 SESSDATA 和 bili_jct 的值，写入 ~/.config/danmu_sender/cookies.txt（格式: SESSDATA=xxx; bili_jct=yyy）")
    print()


def _fetch_live_rooms(cookie: str) -> list[dict[str, Any]] | None:
    print(_style("正在检测关注中正在直播的房间…", color=36))
    try:
        lives = get_following_live_list(cookie)
    except Exception as e:
        logger.exception("获取直播列表失败")
        _print_cookie_help(str(e))
        return None
    return lives


def _prompt_select_room(lives: list[dict[str, Any]]) -> tuple[str, dict[str, Any] | None]:
    while True:
        choice = _prompt_input("输入直播间序号进入；`refresh` 重新检测；`close` 退出：")
        lower = choice.lower()
        if lower == "close":
            logger.info("用户输入 close，退出程序")
            return ("close", None)
        if lower == "refresh":
            logger.info("用户输入 refresh，重新检测直播列表")
            return ("refresh", None)
        try:
            idx = int(choice)
            if 1 <= idx <= len(lives):
                return ("enter", lives[idx - 1])
        except ValueError:
            pass
        print(_style("请输入有效序号或命令。", color=33))


def _show_all_emoji() -> None:
    lines = [f"{k:<8} -> {v}" for k, v in sorted(TEXT_TO_EMOJI.items(), key=lambda x: -len(x[0]))]
    _print_panel("文本 -> emoji 映射表", lines, color=35)


def _run_room_session(cookie: str, room: dict[str, Any]) -> str:
    room_id = str(room["room_id"])
    uname = room["uname"]
    title = room.get("title") or "无标题"
    logger.info("用户选择直播间 room_id=%s uname=%s", room_id, uname)
    _print_panel(
        "已进入直播间",
        [
            f"主播: {uname}",
            f"标题: {_cut(title, _width() - 12)}",
            f"房间号: {room_id}",
            "命令: exit=返回房间列表并重新检测 | close=退出程序",
        ],
        color=32,
    )

    while True:
        _show_emoji_quick_hint()
        msg = _prompt_input("请输入弹幕内容（最多 30 字）：")
        lower = msg.lower()
        if lower == "close":
            logger.info("用户输入 close，退出程序")
            return "close"
        if lower == "exit":
            logger.info("用户输入 exit，返回房间选择并重新检测")
            print(_style("正在返回房间列表并重新检测…\n", color=36))
            return "exit"
        if lower == "help-emoji":
            _show_all_emoji()
            continue
        if not msg:
            print(_style("弹幕不能为空，请重新输入。", color=33))
            continue

        raw_msg = msg
        parsed_msg = replace_text_emoji(msg)
        unmatched = get_unmatched_brackets(parsed_msg)
        if unmatched:
            print(_style("无法识别的 emoji 关键词（未发送）: " + ", ".join(unmatched), color=31))
            print("可用关键词: " + ", ".join(get_available_emoji_keys()))
            print()
            continue

        final_msg = parsed_msg
        truncated = False
        if len(final_msg) > MAX_MSG_LEN:
            final_msg = final_msg[:MAX_MSG_LEN]
            truncated = True

        preview_lines = [
            f"原始输入: {raw_msg}",
            f"表情替换: {parsed_msg}",
            f"实际发送: {final_msg}",
        ]
        if truncated:
            preview_lines.append(f"提示: 超过 {MAX_MSG_LEN} 字，已截断")
        _print_panel("本次发送预览", preview_lines, color=34)

        try:
            send_danmu(cookie, room_id, final_msg)
            print(_style("发送成功。", color=32, bold=True))
        except Exception as e:
            logger.exception("发送弹幕失败 room_id=%s msg=%s", room_id, final_msg)
            print(_style(f"发送失败: {e}", color=31, bold=True))
        print()


def run() -> None:
    setup_logging()
    logger.info("程序启动")

    cookie = load_cookie()
    _print_title("B站直播弹幕发送台", "现代化终端界面 | 表情包快捷输入 | 实时房间重检")

    while True:
        lives = _fetch_live_rooms(cookie)
        if lives is None:
            return
        if not lives:
            logger.info("当前没有关注中的主播在直播")
            _print_panel("暂无直播", ["当前没有关注中的主播在直播。", "输入 refresh 继续检测，或 close 退出。"], color=33)
            action = _prompt_input("请输入命令：").lower()
            if action == "close":
                print("已退出。")
                return
            if action == "refresh":
                continue
            print(_style("无效命令，将继续检测。", color=33))
            continue

        _render_live_list(lives)
        action, room = _prompt_select_room(lives)
        if action == "close":
            print("已退出。")
            return
        if action == "refresh":
            continue
        if room is None:
            continue

        room_action = _run_room_session(cookie, room)
        if room_action == "close":
            print("已退出。")
            return
