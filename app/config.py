"""設定：從 .env 與環境變數讀取，含預設值與驗證。"""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# 專案根目錄（app/ 的上一層），相對路徑一律以這裡為基準，不依賴目前工作目錄
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class ConfigError(Exception):
    """設定有誤時拋出，訊息會指出是哪一個變數。"""


@dataclass
class Config:
    secret_key: str
    max_upload_mb: int = 100
    max_files_per_room: int = 10
    room_ttl_days: int = 30
    owner_session_days: int = 30
    display_name_limit: int = 12
    upload_dir: Path = PROJECT_ROOT / "uploads"
    log_file: Path = PROJECT_ROOT / "logs" / "quickshare.log"
    host: str = "127.0.0.1"
    port: int = 5000
    threads: int = 4
    session_cookie_secure: bool = False
    # 測試時設為 False，就不會啟動每小時一次的背景清理 thread
    start_cleanup_thread: bool = True


def _int(env, name, default):
    """讀取正整數設定；無法轉型或小於 1 時拋出 ConfigError。"""
    raw = env.get(name, "").strip()
    if raw == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ConfigError(f"設定 {name} 必須是整數，目前的值是「{raw}」") from None
    if value < 1:
        raise ConfigError(f"設定 {name} 必須大於或等於 1，目前的值是 {value}")
    return value


def _path(env, name, default):
    """讀取路徑設定；相對路徑以專案根目錄為基準。"""
    path = Path(env.get(name, "").strip() or default)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _bool(env, name, default):
    raw = env.get(name, "").strip().lower()
    if raw == "":
        return default
    if raw in ("true", "1", "yes", "on"):
        return True
    if raw in ("false", "0", "no", "off"):
        return False
    raise ConfigError(f"設定 {name} 必須是 true 或 false，目前的值是「{raw}」")


def load_config(env=None):
    """建立 Config。env 預設為 os.environ（會先讀取專案根目錄的 .env）。"""
    if env is None:
        load_dotenv(PROJECT_ROOT / ".env")
        env = os.environ

    secret_key = env.get("SECRET_KEY", "").strip()
    if not secret_key:
        raise ConfigError(
            "缺少設定 SECRET_KEY。請在 .env 中設定，可用以下指令產生：\n"
            '  python -c "import secrets; print(secrets.token_hex(32))"'
        )

    return Config(
        secret_key=secret_key,
        max_upload_mb=_int(env, "MAX_UPLOAD_MB", 100),
        max_files_per_room=_int(env, "MAX_FILES_PER_ROOM", 10),
        room_ttl_days=_int(env, "ROOM_TTL_DAYS", 30),
        owner_session_days=_int(env, "OWNER_SESSION_DAYS", 30),
        display_name_limit=_int(env, "DISPLAY_NAME_LIMIT", 12),
        upload_dir=_path(env, "UPLOAD_DIR", "uploads"),
        log_file=_path(env, "LOG_FILE", "logs/quickshare.log"),
        host=env.get("HOST", "").strip() or "127.0.0.1",
        port=_int(env, "PORT", 5000),
        threads=_int(env, "THREADS", 4),
        session_cookie_secure=_bool(env, "SESSION_COOKIE_SECURE", False),
    )
