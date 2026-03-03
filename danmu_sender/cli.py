"""终端交互：展示关注直播列表、选择直播间、输入并发送弹幕。"""
from .bilibili_api import get_following_live_list, send_danmu
from .cookie_loader import get_last_chrome_failure, load_cookie
from .emoji_map import (
    replace_text_emoji,
    TEXT_TO_EMOJI,
    get_emoji_help_lines,
    get_unmatched_brackets,
    get_available_emoji_keys,
)
from .logging_config import setup_logging, get_logger

MAX_MSG_LEN = 30
logger = get_logger("cli")


def run() -> None:
    setup_logging()
    logger.info("程序启动")
    cookie = load_cookie()
    print("正在获取关注中的直播列表…")
    try:
        lives = get_following_live_list(cookie)
    except Exception as e:
        logger.exception("获取直播列表失败")
        err_msg = str(e)
        print(f"获取直播列表失败: {err_msg}")
        if "未登录" in err_msg or "4100000" in err_msg:
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
        return
    if not lives:
        logger.info("当前没有关注中的主播在直播")
        print("当前没有关注中的主播在直播。")
        return
    print("\n--- 关注中正在直播 ---")
    for i, item in enumerate(lives, 1):
        title = (item["title"] or "无标题")[:50]
        print(f"  {i}. {item['uname']} | {title}")
    print()
    while True:
        choice = input("请输入要进入的直播间序号（输入 close 退出程序）: ").strip()
        if choice.lower() == "close":
            logger.info("用户输入 close，退出程序")
            print("已退出。")
            return
        try:
            idx = int(choice)
            if 1 <= idx <= len(lives):
                break
        except ValueError:
            pass
        print("请输入有效序号。")
    room_id = lives[idx - 1]["room_id"]
    uname = lives[idx - 1]["uname"]
    logger.info("用户选择直播间 room_id=%s uname=%s", room_id, uname)
    print(f"\n已选择: {uname}")
    for line in get_emoji_help_lines():
        print(line)
    while True:
        msg = input("请输入要发送的弹幕（最多 30 字；close=退出，exit=换房间，空=重输，help-emoji=查看映射）: ").strip()
        if msg.lower() == "close":
            logger.info("用户输入 close，退出程序")
            print("已退出。")
            return
        if msg.lower() == "exit":
            logger.info("用户输入 exit，回到选择直播间")
            print("返回选择直播间。\n")
            break
        if msg.lower() == "help-emoji":
            print("--- 文本 → emoji 映射表 ---")
            for k, v in sorted(TEXT_TO_EMOJI.items(), key=lambda x: -len(x[0])):
                print(f"  {k} → {v}")
            print()
            continue
        if not msg:
            print("弹幕不能为空，请重新输入。")
            continue
        orig = msg
        msg = replace_text_emoji(msg)
        unmatched = get_unmatched_brackets(msg)
        if unmatched:
            print("无法识别的 emoji 关键词（未发送）:", ", ".join(unmatched))
            print("可用关键词:", ", ".join(get_available_emoji_keys()))
            print()
            continue
        if msg != orig:
            print(f"  → 将发送: {msg}")
        if len(msg) > MAX_MSG_LEN:
            print(f"超过 {MAX_MSG_LEN} 字，已截断。")
            msg = msg[:MAX_MSG_LEN]
        try:
            send_danmu(cookie, room_id, msg)
            print("发送成功。")
        except Exception as e:
            logger.exception("发送弹幕失败 room_id=%s msg=%s", room_id, msg)
            print(f"发送失败: {e}")
        print()
