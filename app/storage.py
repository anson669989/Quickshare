"""儲存層：整個專案中唯一直接碰檔案系統的模組。"""
import logging
import os
import re
import secrets
import shutil
import time
import unicodedata
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("quickshare")

# 房間 ID：10 碼小寫英數（約 52 bits）。Windows 不分大小寫，所以只用小寫
ROOM_ID_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyz"
ROOM_ID_LENGTH = 10
ROOM_ID_RE = re.compile(r"^[0-9a-z]{10}$")
# 儲存檔名：<8 碼 uid>_<安全檔名>
STORED_NAME_RE = re.compile(r"^[0-9a-f]{8}_[一-鿿A-Za-z0-9._-]+$")
# 上傳中的暫存檔：<8 碼 uid>.part
TEMP_NAME_RE = re.compile(r"^[0-9a-f]{8}\.part$")
# 安全檔名中「不允許」的字元
UNSAFE_CHARS_RE = re.compile(r"[^一-鿿A-Za-z0-9._-]")

MAX_SAFE_NAME_LENGTH = 150
CHUNK_SIZE = 1024 * 1024


class StorageError(Exception):
    """儲存層自訂例外的共同父類別。"""


class InvalidRoomId(StorageError):
    """房間 ID 格式不正確。"""


class InvalidFilename(StorageError):
    """檔名清理後是空的，或路徑不安全。"""


class FileTooLarge(StorageError):
    """檔案本體超過上限。"""


def new_room_id():
    """用 secrets 逐字均勻挑選，產生 10 碼房間 ID。"""
    return "".join(secrets.choice(ROOM_ID_ALPHABET) for _ in range(ROOM_ID_LENGTH))


def is_valid_room_id(room_id):
    return isinstance(room_id, str) and ROOM_ID_RE.fullmatch(room_id) is not None


def check_room_id(room_id):
    if not is_valid_room_id(room_id):
        raise InvalidRoomId(room_id)


def safe_filename(name):
    """把使用者上傳的檔名轉成安全檔名；結果為空時拋出 InvalidFilename。"""
    # 1. 同時以 / 與 \ 切割，只取最後一段
    name = re.split(r"[/\\]", name or "")[-1]
    # 2. Unicode 正規化為 NFC
    name = unicodedata.normalize("NFC", name)
    # 3. 空白轉成底線
    name = re.sub(r"\s", "_", name)
    # 4. 只保留中文、英數、. _ -
    name = UNSAFE_CHARS_RE.sub("", name)
    # 5. 去掉開頭與結尾的 .
    name = name.strip(".")
    # 6. 長度上限：截斷主檔名、保留副檔名
    if len(name) > MAX_SAFE_NAME_LENGTH:
        stem, dot, ext = name.rpartition(".")
        if dot and len(ext) + 1 < MAX_SAFE_NAME_LENGTH:
            ext = "." + ext
            name = stem[: MAX_SAFE_NAME_LENGTH - len(ext)] + ext
        else:
            name = name[:MAX_SAFE_NAME_LENGTH]
    # 7. 結果為空就拒絕
    if not name:
        raise InvalidFilename(name)
    return name


def display_name(stored_name):
    """儲存名去掉 uid 前綴，即為顯示名與下載名。"""
    return stored_name.split("_", 1)[1]


def format_size(size):
    """把 bytes 轉成好讀的大小（Jinja filter）。"""
    if size < 1024:
        return f"{size} bytes"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} kB"
    return f"{size / 1024 / 1024:.1f} MB"


def shorten_name(name, limit):
    """檔名過長時中間以 ... 省略，前後各保留 limit 字並保留副檔名（Jinja filter）。"""
    stem, ext = os.path.splitext(name)
    if len(stem) <= limit * 2:
        return name
    return f"{stem[:limit]}...{stem[-limit:]}{ext}"


class Storage:
    def __init__(self, config):
        self.upload_dir = Path(config.upload_dir)
        self.max_bytes = config.max_upload_mb * 1024 * 1024
        self.max_files = config.max_files_per_room
        self.ttl_seconds = config.room_ttl_days * 24 * 60 * 60

    # ---------- 路徑安全：所有讀、寫、刪都經過這裡 ----------
    def _path(self, room_id, name=None, allow_temp=False):
        check_room_id(room_id)
        room_dir = (self.upload_dir / room_id).resolve()
        if not room_dir.is_relative_to(self.upload_dir.resolve()):
            raise InvalidRoomId(room_id)
        if name is None:
            return room_dir
        if not (STORED_NAME_RE.fullmatch(name) or (allow_temp and TEMP_NAME_RE.fullmatch(name))):
            raise InvalidFilename(name)
        path = (room_dir / name).resolve()
        if not path.is_relative_to(room_dir) or path == room_dir:
            raise InvalidFilename(name)
        return path

    # ---------- 讀取 ----------
    def list_files(self, room_id):
        """回傳房間內的檔案（新到舊）。純讀取，不刪除任何東西。"""
        room_dir = self._path(room_id)
        if not room_dir.is_dir():
            return []
        files = []
        for entry in room_dir.iterdir():
            if not STORED_NAME_RE.fullmatch(entry.name) or not entry.is_file():
                continue
            stat = entry.stat()
            files.append({
                "stored_name": entry.name,
                "display_name": display_name(entry.name),
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
                "modified": datetime.fromtimestamp(stat.st_mtime),
            })
        files.sort(key=lambda f: f["mtime_ns"], reverse=True)
        return files

    def get_file(self, room_id, stored_name):
        """回傳檔案路徑；檔名不合格式或檔案不存在時回傳 None。"""
        try:
            path = self._path(room_id, stored_name)
        except InvalidFilename:
            return None
        return path if path.is_file() else None

    # ---------- 寫入 ----------
    def save_file(self, room_id, upload):
        """儲存上傳檔案，回傳儲存名。檔名不合法或太大時拋出例外。"""
        safe = safe_filename(upload.filename)
        room_dir = self._path(room_id)
        existing = self.list_files(room_id)
        room_dir.mkdir(parents=True, exist_ok=True)

        uid = secrets.token_hex(4)
        temp_path = self._path(room_id, f"{uid}.part", allow_temp=True)
        final_path = self._path(room_id, f"{uid}_{safe}")
        try:
            written = 0
            with open(temp_path, "wb") as out:
                while chunk := upload.stream.read(CHUNK_SIZE):
                    written += len(chunk)
                    if written > self.max_bytes:
                        raise FileTooLarge(upload.filename)
                    out.write(chunk)
            os.replace(temp_path, final_path)
        except BaseException:
            temp_path.unlink(missing_ok=True)
            raise

        # 確保新檔案的修改時間一定比舊檔案新（連續快速上傳時時間可能相同）
        newest = existing[0]["mtime_ns"] if existing else 0
        new_time = max(time.time_ns(), newest + 10_000_000)
        os.utime(final_path, ns=(new_time, new_time))

        self._enforce_quota(room_id)
        return final_path.name

    def _enforce_quota(self, room_id):
        """只保留最新的 max_files 個檔案。"""
        for old in self.list_files(room_id)[self.max_files:]:
            self._path(room_id, old["stored_name"]).unlink(missing_ok=True)
            logger.info("超過配額，刪除舊檔案：%s/%s", room_id, old["stored_name"])

    # ---------- 刪除 ----------
    def delete_file(self, room_id, stored_name):
        """刪除檔案，回傳是否成功。"""
        path = self.get_file(room_id, stored_name)
        if path is None:
            return False
        path.unlink()
        return True

    def purge_expired_rooms(self):
        """刪除超過期限沒有新上傳的房間，回傳刪除的房間數。"""
        if not self.upload_dir.is_dir():
            return 0
        now = time.time()
        removed = 0
        for room_dir in self.upload_dir.iterdir():
            # 只處理名稱符合房間 ID 格式的一般資料夾，其他一律不碰
            if not ROOM_ID_RE.fullmatch(room_dir.name):
                continue
            if room_dir.is_symlink() or room_dir.is_junction() or not room_dir.is_dir():
                continue
            mtimes = [f.stat().st_mtime for f in room_dir.iterdir() if f.is_file()]
            last_activity = max(mtimes) if mtimes else room_dir.stat().st_mtime
            if now - last_activity > self.ttl_seconds:
                shutil.rmtree(room_dir)
                removed += 1
                logger.info("房間過期，已刪除：%s", room_dir.name)
        return removed
