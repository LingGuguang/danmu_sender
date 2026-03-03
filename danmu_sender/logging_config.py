"""日志配置：输出到 danmu_sender/runtime/logs，单文件满 500MB 切分。"""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

# 项目根目录：danmu_sender/（即包含 main.py 的目录）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUNTIME_DIR = _PROJECT_ROOT / "runtime"
LOG_DIR = RUNTIME_DIR / "logs"
LOG_FILE = LOG_DIR / "danmu_sender.log"

# 单文件最大 500MB 后切分，保留最多 5 个备份
MAX_BYTES = 500 * 1024 * 1024
BACKUP_COUNT = 5

# 含 文件名:行号 函数名，便于定位错误
_FORMAT = "%(asctime)s [%(levelname)s] %(name)s | %(filename)s:%(lineno)d %(funcName)s() | %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"


def _ensure_log_dir() -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    return LOG_DIR


def setup_logging(
    level: int = logging.INFO,
    to_console: bool = True,
) -> logging.Logger:
    """
    配置并返回主 logger。将日志写入 runtime/logs/danmu_sender.log，
    单文件达到 500MB 时切分（保留 5 个备份）。
    """
    _ensure_log_dir()
    logger = logging.getLogger("danmu_sender")
    if logger.handlers:
        return logger
    logger.setLevel(level)
    formatter = logging.Formatter(_FORMAT, datefmt=_DATE_FMT)

    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    if to_console:
        console = logging.StreamHandler(sys.stderr)
        console.setFormatter(formatter)
        logger.addHandler(console)

    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """获取 logger。若尚未 setup，会先执行一次 setup_logging。"""
    main = logging.getLogger("danmu_sender")
    if not main.handlers:
        setup_logging()
    if name:
        return logging.getLogger(f"danmu_sender.{name}")
    return main
