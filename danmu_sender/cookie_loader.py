"""从 Chrome、请求 B 站响应或本地文件加载 B站 Cookie。"""
import json
import os
import re
from pathlib import Path
from typing import Optional

from .logging_config import get_logger

logger = get_logger("cookie")

# 可选：从 Chrome 读取
try:
    import browser_cookie3
    HAS_BROWSER_COOKIE = True
except ImportError:
    HAS_BROWSER_COOKIE = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# B站相关域名
BILIBILI_DOMAINS = (".bilibili.com", ".live.bilibili.com", ".api.bilibili.com")

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# 模仿 Chrome 访问文档页的完整请求头，便于拿到与浏览器一致的 Set-Cookie
CHROME_LIKE_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "max-age=0",
    "Sec-Ch-Ua": '"Not A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Linux"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}


def _cookie_file_path() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))) / "danmu_sender" / "cookies.txt"


# 记录上次从 Chrome 读取失败的原因，便于在「未登录」时给用户提示
_last_chrome_failure: Optional[str] = None


def load_from_chrome() -> Optional[str]:
    """从 Chrome 读取 B站 Cookie 字符串。失败返回 None。"""
    global _last_chrome_failure
    _last_chrome_failure = None
    if not HAS_BROWSER_COOKIE:
        _last_chrome_failure = "未安装 browser_cookie3"
        logger.debug("browser_cookie3 未安装，跳过从 Chrome 读取")
        return None
    try:
        cj = browser_cookie3.chrome(domain_name=".bilibili.com")
        parts = []
        for c in cj:
            if c.name in ("SESSDATA", "bili_jct", "DedeUserID", "DedeUserID__ckMd5", "sid"):
                parts.append(f"{c.name}={c.value}")
        if not parts:
            _last_chrome_failure = "Chrome 中未找到 B 站登录 Cookie（可能未在 Chrome 登录 B 站）"
            logger.debug("Chrome 中未找到 B站 关键 Cookie")
            return None
        logger.info("已从 Chrome 读取 B站 Cookie")
        return "; ".join(parts)
    except Exception as e:
        err = str(e).strip()
        _last_chrome_failure = err or type(e).__name__
        logger.debug("从 Chrome 读取 Cookie 失败: %s", e)
        # 部分环境只有 Chromium，再试一次
        try:
            cj = browser_cookie3.chromium(domain_name=".bilibili.com")
            parts = []
            for c in cj:
                if c.name in ("SESSDATA", "bili_jct", "DedeUserID", "DedeUserID__ckMd5", "sid"):
                    parts.append(f"{c.name}={c.value}")
            if parts:
                _last_chrome_failure = None
                logger.info("已从 Chromium 读取 B站 Cookie")
                return "; ".join(parts)
        except Exception:
            pass
        return None


def get_last_chrome_failure() -> Optional[str]:
    """返回最近一次从 Chrome 读取 Cookie 失败的原因（用于提示用户）。"""
    return _last_chrome_failure


def _parse_initial_state_and_scripts(text: str) -> dict[str, str]:
    """从响应体中解析 __INITIAL_STATE__ 与脚本里藏匿的 cookie/token，返回 name -> value。"""
    found: dict[str, str] = {}
    if not text or len(text) < 500:
        return found
    # 1) 脚本里常见写法: "SESSDATA"="xxx", 'bili_jct':'xxx'
    for name in ("SESSDATA", "bili_jct", "DedeUserID", "csrf", "sid"):
        for pattern in (
            rf'["\']{name}["\']?\s*[:=]\s*["\']([^"\']+)',
            rf"{name}\s*=\s*[\"']([^\"']+)",
        ):
            m = re.search(pattern, text[:300000], re.I)
            if m and len(m.group(1)) > 4:
                found[name] = m.group(1).strip()
    # 2) __INITIAL_STATE__ 为 JSON，可能嵌套 cookie / user 信息
    state_m = re.search(
        r"window\.__INITIAL_STATE__\s*=\s*(\{.+?\});\s*\(function",
        text,
        re.DOTALL,
    )
    if not state_m:
        state_m = re.search(r"__INITIAL_STATE__\s*=\s*(\{[^<]+?\});", text)
    if state_m:
        try:
            state = json.loads(state_m.group(1))
            # 扁平遍历找可能存 cookie 的字段
            def _walk(obj, depth=0):
                if depth > 5:
                    return
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        if k in ("bili_jct", "csrf", "SESSDATA", "sid", "DedeUserID") and isinstance(v, str) and len(v) > 4:
                            found[k] = v
                        _walk(v, depth + 1)
                elif isinstance(obj, (list, tuple)):
                    for x in obj:
                        _walk(x, depth + 1)
            _walk(state)
        except (json.JSONDecodeError, TypeError):
            pass
    return found


def _request_homepage_chrome_like(session: requests.Session, url: str = "https://www.bilibili.com") -> Optional[str]:
    """
    用 Chrome 风格请求头访问 B 站主页，跟随重定向，汇总所有 Set-Cookie 并解析响应体中的 token。
    返回合并后的 cookie 字符串（仅从本次请求链与响应体得到）。
    """
    try:
        r = session.get(url, timeout=14, allow_redirects=True)
        r.raise_for_status()
    except requests.RequestException as e:
        logger.debug("请求主页失败 %s: %s", url, e)
        return None
    # 响应体里藏匿的 token（__INITIAL_STATE__、脚本等）
    embedded = _parse_initial_state_and_scripts(r.text)
    for name, value in embedded.items():
        session.cookies.set(name, value, domain=".bilibili.com")
    # 重定向链里每一跳的 Set-Cookie 已由 Session 自动合并
    if not session.cookies:
        return None
    return "; ".join(f"{c.name}={c.value}" for c in session.cookies)


def load_from_bilibili_request(initial_cookie: Optional[str] = None) -> Optional[str]:
    """
    模仿 Chrome 发送主页请求，从响应头 Set-Cookie 与响应体（__INITIAL_STATE__、脚本）中提取 Cookie。
    - 若传入 initial_cookie（如从文件读到的旧 cookie），会先带该 cookie 访问主页，尝试触发服务端刷新/续期并拿到新 Set-Cookie。
    - 未登录且无 initial_cookie 时只能拿到匿名 Cookie（b_nut、buvid3）。
    """
    if not HAS_REQUESTS:
        logger.debug("requests 不可用，跳过请求 B 站")
        return None
    try:
        session = requests.Session()
        session.headers.update(CHROME_LIKE_HEADERS)
        if initial_cookie:
            for part in initial_cookie.split(";"):
                part = part.strip()
                if "=" in part:
                    k, v = part.split("=", 1)
                    session.cookies.set(k.strip(), v.strip(), domain=".bilibili.com")
            logger.debug("带已有 Cookie 访问主页以尝试刷新")
        # 先访问主站（与“点进 bilibili 主页”一致），再访问直播页以收齐域名下 Cookie
        for url in ("https://www.bilibili.com", "https://live.bilibili.com/"):
            cookie_str = _request_homepage_chrome_like(session, url)
            if cookie_str and any(
                name in cookie_str
                for name in ("SESSDATA", "bili_jct", "DedeUserID")
            ):
                logger.info("已从 B 站主页响应中提取到登录态 Cookie")
                return cookie_str
        if not session.cookies:
            logger.debug("请求 B 站未得到任何 Cookie")
            return None
        cookie_str = "; ".join(f"{c.name}={c.value}" for c in session.cookies)
        logger.info("已从 B 站响应提取 Cookie（共 %s 项）", len(session.cookies))
        return cookie_str
    except Exception as e:
        logger.debug("从 B 站请求提取 Cookie 失败: %s", e)
        return None


def load_from_file() -> Optional[str]:
    """从 ~/.config/danmu_sender/cookies.txt 读取 Cookie。"""
    path = _cookie_file_path()
    if not path.exists():
        logger.debug("Cookie 文件不存在: %s", path)
        return None
    try:
        raw = path.read_text(encoding="utf-8").strip()
        # 允许文件里带 "Cookie: " 前缀，自动去掉
        if raw.lower().startswith("cookie:"):
            raw = raw.split(":", 1)[1].strip()
        if raw:
            logger.info("已从文件读取 B站 Cookie: %s", path)
        return raw if raw else None
    except Exception as e:
        logger.warning("读取 Cookie 文件失败 %s: %s", path, e)
        return None


def _ensure_config_dir() -> Path:
    """确保配置目录存在，返回 Cookie 文件路径。"""
    path = _cookie_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _has_login_cookie(cookie_str: str) -> bool:
    """判断 cookie 字符串是否包含登录态（SESSDATA 或 bili_jct）。"""
    if not cookie_str:
        return False
    lower = cookie_str.lower()
    return "sessdata" in lower or "bili_jct" in lower


def load_cookie() -> str:
    """
    按顺序尝试：Chrome → 请求 B 站并分析响应提取 Cookie → 配置文件 → 交互式粘贴。
    拿到来自 Chrome 或文件的 Cookie 后，会再模仿 Chrome 访问主页，尝试从响应中刷新/续期 Cookie。
    """
    cookie = load_from_chrome()
    if cookie:
        refreshed = load_from_bilibili_request(initial_cookie=cookie)
        if refreshed and _has_login_cookie(refreshed):
            return refreshed
        return cookie

    cookie = load_from_bilibili_request()
    if cookie:
        return cookie

    cookie = load_from_file()
    if cookie:
        refreshed = load_from_bilibili_request(initial_cookie=cookie)
        if refreshed and _has_login_cookie(refreshed):
            logger.info("已通过访问主页刷新配置文件中的 Cookie")
            return refreshed
        return cookie

    path = _ensure_config_dir()
    logger.error("无法获取 B站 Cookie（Chrome、请求 B 站、文件均失败）")

    # 交互式：询问是否现在粘贴 Cookie 并保存
    try:
        print(
            "\n未检测到 B站 Cookie。可将浏览器中复制的 Cookie 粘贴到配置文件，或现在粘贴。\n"
            f"  配置文件路径：{path}\n"
            "  获取方式：bilibili.com 登录后 F12 → Network → 任选请求 → Request Headers 中复制 Cookie\n"
        )
        choice = input("是否现在粘贴 Cookie 并保存？(y/n，直接回车=n): ").strip().lower()
        if choice == "y" or choice == "yes":
            print("请粘贴 Cookie（粘贴后回车，再按一次回车结束）：")
            lines = []
            while True:
                line = input()
                if not line and lines:
                    break
                if not line:
                    continue
                lines.append(line)
            raw = " ".join(lines).strip()
            if raw:
                if raw.lower().startswith("cookie:"):
                    raw = raw.split(":", 1)[1].strip()
                path.write_text(raw, encoding="utf-8")
                logger.info("已保存 Cookie 到文件并重试: %s", path)
                cookie = load_from_file()
                if cookie:
                    return cookie
    except EOFError:
        pass

    raise RuntimeError(
        "无法获取 B站 Cookie。请确保：\n"
        "  1) 已用 Chrome 登录 B站，且本机可读取 Chrome Cookie；或\n"
        f"  2) 将 Cookie 写入文件：{path}\n"
        "     （在 bilibili.com 登录后 F12 → Network → 任选请求 → Request Headers 中复制 Cookie）\n"
        "  程序已尝试从 Chrome、请求 B 站响应和配置文件中获取 Cookie，均未得到可用登录态。"
    )


def cookie_to_dict(cookie_str: str) -> dict:
    """将 Cookie 字符串转为 requests 可用的 dict。"""
    result = {}
    for part in cookie_str.split(";"):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            result[k.strip()] = v.strip()
    return result
