"""儲存層與設定的單元測試（測試類別 1、8、10）。"""
import os
import time

import pytest

from app import storage
from app.config import PROJECT_ROOT, ConfigError, load_config
from app.storage import InvalidFilename, InvalidRoomId, Storage, safe_filename


# ---------- 1. 檔名清理 ----------
def test_chinese_is_kept():
    assert safe_filename("報告.pdf") == "報告.pdf"


def test_spaces_become_underscores():
    assert safe_filename("my file 檔案.txt") == "my_file_檔案.txt"


@pytest.mark.parametrize("raw, expected", [
    ("a/b.txt", "b.txt"),
    ("a\\b.txt", "b.txt"),
    ("..\\..\\x", "x"),
    ("../../etc/passwd", "passwd"),
    ("C:\\Users\\me\\秘密.docx", "秘密.docx"),
])
def test_path_parts_are_removed(raw, expected):
    assert safe_filename(raw) == expected


@pytest.mark.parametrize("raw", ["", "..", "...", "???", "<>|*", "a/..", "@#$%"])
def test_all_illegal_raises(raw):
    with pytest.raises(InvalidFilename):
        safe_filename(raw)


def test_leading_and_trailing_dots_removed():
    assert safe_filename(".hidden.txt.") == "hidden.txt"


def test_nfc_normalization():
    # 「é」以分解形式（e + 結合重音）輸入，正規化後才會被當成一個字元處理
    assert safe_filename("cafe\u0301.txt") == "caf.txt"
    assert safe_filename("\u5831\u544a.txt") == "報告.txt"


def test_long_name_is_truncated_keeping_extension():
    result = safe_filename("a" * 300 + ".txt")
    assert len(result) == 150
    assert result.endswith(".txt")
    assert result.startswith("aaaa")


def test_shorten_name_keeps_extension():
    assert storage.shorten_name("short.txt", 3) == "short.txt"
    assert storage.shorten_name("abcdefghij.txt", 3) == "abc...hij.txt"


def test_format_size():
    assert storage.format_size(500) == "500 bytes"
    assert storage.format_size(2048) == "2.0 kB"
    assert storage.format_size(3 * 1024 * 1024) == "3.0 MB"


def test_invalid_room_id_raises(config):
    store = Storage(config)
    for bad in ["..", "A" * 10, "a" * 9, "a" * 11, "aaaa_aaaaa", "0123456789abcdef0123456789abcdef", "..\\" + "a" * 7]:
        with pytest.raises(InvalidRoomId):
            store.list_files(bad)


def test_bad_names_are_treated_as_missing(config, tmp_path):
    store = Storage(config)
    room = storage.new_room_id()
    secret = tmp_path / "secret.txt"
    secret.write_text("secret")
    for bad in ["..\\..\\secret.txt", "../../secret.txt", "abcd1234_..", "secret.txt", "ABCD1234_x.txt"]:
        assert store.get_file(room, bad) is None
        assert store.delete_file(room, bad) is False
    assert secret.exists()


# ---------- 8. 過期清理 ----------
def make_room(upload_dir, room_id, filename="0123abcd_a.txt"):
    room_dir = upload_dir / room_id
    room_dir.mkdir(parents=True)
    (room_dir / filename).write_text("x")
    return room_dir


def set_age(path, days):
    old = time.time() - days * 24 * 60 * 60
    os.utime(path, (old, old))


def test_purge_expired_rooms(config):
    store = Storage(config)
    upload_dir = config.upload_dir

    expired = make_room(upload_dir, "a" * 10)
    set_age(expired / "0123abcd_a.txt", 31)

    fresh = make_room(upload_dir, "b" * 10)

    empty_expired = upload_dir / ("c" * 10)
    empty_expired.mkdir()
    set_age(empty_expired, 31)

    other = upload_dir / "not-a-room"
    other.mkdir()
    (other / "keep.txt").write_text("x")
    set_age(other / "keep.txt", 365)
    set_age(other, 365)

    upper = upload_dir / ("D" * 10)  # 大寫不符合房間 ID 格式
    upper.mkdir()
    set_age(upper, 365)

    old_format = upload_dir / ("e" * 32)  # 舊格式（32 碼）也不碰
    old_format.mkdir()
    set_age(old_format, 365)

    assert store.purge_expired_rooms() == 2
    assert not expired.exists()
    assert not empty_expired.exists()
    assert fresh.exists()
    assert (other / "keep.txt").exists()
    assert upper.exists()
    assert old_format.exists()


# ---------- 房間 ID ----------
def test_new_room_id_format():
    for _ in range(200):
        room = storage.new_room_id()
        assert len(room) == 10
        assert storage.is_valid_room_id(room)


def test_new_room_id_uses_whole_alphabet():
    # 字元集是小寫英數（不只 hex），且每個字元都會出現
    seen = set("".join(storage.new_room_id() for _ in range(2000)))
    assert seen == set("0123456789abcdefghijklmnopqrstuvwxyz")


def test_purge_without_upload_dir(config):
    assert Storage(config).purge_expired_rooms() == 0


# ---------- 10. 設定 ----------
def test_missing_secret_key():
    with pytest.raises(ConfigError, match="SECRET_KEY"):
        load_config({})


@pytest.mark.parametrize("name, value", [
    ("MAX_UPLOAD_MB", "abc"),
    ("MAX_UPLOAD_MB", "0"),
    ("MAX_FILES_PER_ROOM", "-3"),
    ("ROOM_TTL_DAYS", "1.5"),
    ("OWNER_SESSION_DAYS", "x"),
    ("DISPLAY_NAME_LIMIT", "0"),
    ("PORT", "port"),
    ("THREADS", "0"),
])
def test_invalid_numbers(name, value):
    with pytest.raises(ConfigError, match=name):
        load_config({"SECRET_KEY": "k", name: value})


def test_invalid_bool():
    with pytest.raises(ConfigError, match="SESSION_COOKIE_SECURE"):
        load_config({"SECRET_KEY": "k", "SESSION_COOKIE_SECURE": "maybe"})


def test_defaults_and_relative_paths():
    config = load_config({"SECRET_KEY": "k"})
    assert config.max_upload_mb == 100
    assert config.max_files_per_room == 10
    assert config.room_ttl_days == 30
    assert config.owner_session_days == 30
    assert config.display_name_limit == 12
    assert config.host == "127.0.0.1"
    assert config.port == 5000
    assert config.threads == 4
    assert config.session_cookie_secure is False
    # 相對路徑以專案根目錄為基準，而不是目前工作目錄
    assert config.upload_dir == PROJECT_ROOT / "uploads"
    assert config.log_file == PROJECT_ROOT / "logs" / "quickshare.log"
