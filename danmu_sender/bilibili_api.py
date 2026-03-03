"""B站直播相关 API：关注中的直播列表、发送弹幕。"""
import time
from typing import Any

import requests

from .cookie_loader import cookie_to_dict, load_cookie
from .logging_config import get_logger

logger = get_logger("api")

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
API_VC = "https://api.vc.bilibili.com"
API_LIVE = "https://api.live.bilibili.com"


def _session(cookie_str: str, referer: str = "https://live.bilibili.com/") -> requests.Session:
    s = requests.Session()
    s.cookies.update(cookie_to_dict(cookie_str))
    s.headers.update({
        "User-Agent": USER_AGENT,
        "Origin": "https://live.bilibili.com",
        "Referer": referer,
    })
    return s


def get_following_live_list(cookie_str: str, size: int = 50) -> list[dict[str, Any]]:
    """
    获取当前账号「关注中」正在直播的用户列表。
    返回列表项包含: room_id, uname, title, link 等。
    """
    url = f"{API_VC}/dynamic_svr/v1/dynamic_svr/w_live_users"
    s = _session(cookie_str)
    logger.debug("请求关注直播列表 size=%s", size)
    r = s.get(url, params={"size": size}, timeout=10)
    r.raise_for_status()
    data = r.json()
    if data.get("code") != 0:
        logger.error("关注直播列表 API 错误: %s", data)
        raise RuntimeError(f"B站 API 返回错误: {data.get('message', data)}")
    # 有的接口 data 在 data 里，有的直接是 data
    body = data.get("data") or data
    items = body.get("items") or body.get("list") or []
    result = []
    for item in items:
        # 可能字段: room_id, uid, uname, title, link, face 等
        room_id = item.get("room_id") or item.get("roomid")
        if not room_id and item.get("link"):
            # link 形如 https://live.bilibili.com/123456 或 .../123456?query=...
            try:
                segment = item["link"].rstrip("/").split("/")[-1]
                room_id = segment.split("?")[0] if "?" in segment else segment
            except Exception:
                continue
        if not room_id:
            continue
        # 确保 room_id 仅为房间号（去掉可能带上的 ? 及后续参数）
        room_id = str(room_id).split("?")[0].strip()
        result.append({
            "room_id": str(room_id),
            "uname": item.get("uname") or item.get("name") or "未知",
            "title": item.get("title") or "无标题",
            "link": item.get("link") or f"https://live.bilibili.com/{room_id}",
        })
    logger.info("获取关注直播列表成功，共 %s 个直播间", len(result))
    return result


def get_real_room_id(cookie_str: str, short_room_id: str) -> str:
    """
    通过 room_init 将短号/展示号转为真实房间号。
    B站发弹幕等接口需要真实 room_id。
    """
    url = f"{API_LIVE}/room/v1/Room/room_init"
    s = _session(cookie_str)
    r = s.get(url, params={"id": short_room_id}, timeout=10)
    r.raise_for_status()
    data = r.json()
    if data.get("code") != 0:
        raise RuntimeError(f"获取真实房间号失败: {data.get('message', data)}")
    body = data.get("data") or {}
    real_id = body.get("room_id")
    if real_id is None:
        raise RuntimeError("room_init 未返回 room_id")
    return str(real_id)


def send_danmu(cookie_str: str, room_id: str, msg: str) -> None:
    """
    在指定直播间发送一条弹幕。
    room_id: 直播间房间号（可短号，接口会解析）。
    msg: 弹幕内容，建议不超过 30 字。
    """
    if not msg or not msg.strip():
        raise ValueError("弹幕内容不能为空")
    msg = msg.strip()
    cookies = cookie_to_dict(cookie_str)
    csrf = cookies.get("bili_jct") or cookies.get("csrf")
    if not csrf:
        raise RuntimeError("Cookie 中缺少 bili_jct（csrf），请重新复制完整 Cookie")
    # 短号需转为真实房间号，否则接口返回 -400
    real_room_id = get_real_room_id(cookie_str, str(room_id))
    url = f"{API_LIVE}/msg/send"
    referer = f"https://live.bilibili.com/{room_id}"
    s = _session(cookie_str, referer=referer)
    # 接口要求参数名为 roomid（与页面/文档一致）
    payload = {
        "bubble": "0",
        "msg": msg,
        "color": "16777215",
        "mode": "1",
        "fontsize": "25",
        "rnd": str(int(time.time())),
        "roomid": real_room_id,
        "csrf": csrf,
        "csrf_token": csrf,
    }
    logger.info("发送弹幕 room_id=%s real_room_id=%s msg=%s", room_id, real_room_id, msg)
    r = s.post(url, data=payload, timeout=10)
    r.raise_for_status()
    data = r.json()
    if data.get("code") != 0:
        logger.error("发送弹幕 API 错误: %s", data)
        raise RuntimeError(f"发送弹幕失败: {data.get('message', data)}")
    logger.info("弹幕发送成功 room_id=%s", room_id)
