"""路由測試（測試類別 2–7、9、11 與錯誤處理）。"""
import io

import pytest

from app import messages
from tests.conftest import csrf_token, room_of, upload


def files_on_disk(config):
    if not config.upload_dir.exists():
        return []
    return sorted(p.name for p in config.upload_dir.rglob("*") if p.is_file())


# ---------- 2. 路徑穿越 ----------
@pytest.fixture
def secrets_outside(config, tmp_path):
    """在房間外放幾個不該被碰到的檔案。"""
    outside = tmp_path / "secret.txt"
    outside.write_text("TOP-SECRET")
    config.upload_dir.mkdir(parents=True, exist_ok=True)
    in_upload_dir = config.upload_dir / "secret.txt"
    in_upload_dir.write_text("TOP-SECRET")
    other_room = config.upload_dir / ("f" * 32)
    other_room.mkdir()
    other_file = other_room / "0123abcd_other.txt"
    other_file.write_text("TOP-SECRET")
    return [outside, in_upload_dir, other_file]


BAD_ROOM_IDS = [
    "..", "..%5C..", "..%2F..", "%2E%2E", "a" * 31, "a" * 33, "g" * 32, "A" * 32,
    "..%5C" + "f" * 32, "a" * 30 + "..",
]
BAD_FILENAMES = [
    "..", "..%5C..%5Csecret.txt", "..%2F..%2Fsecret.txt", "..%5Csecret.txt",
    "%2E%2E%5Csecret.txt", "secret.txt", "..%5C" + "f" * 32 + "%5C0123abcd_other.txt",
    "0123abcd_..", "0123abcd_..%5C..%5Csecret.txt", "ZZZZZZZZ_x.txt",
]


@pytest.mark.parametrize("bad_room", BAD_ROOM_IDS)
def test_bad_room_ids_are_rejected(client, secrets_outside, bad_room):
    for url in [f"/share_view/{bad_room}", f"/qrcode/{bad_room}", f"/download/{bad_room}/0123abcd_other.txt"]:
        response = client.get(url)
        assert response.status_code == 404, url
        assert b"TOP-SECRET" not in response.data
    token = csrf_token(client)
    response = client.post(f"/remove/{bad_room}/0123abcd_other.txt", data={"csrf_token": token})
    assert response.status_code in (403, 404)
    assert all(p.exists() for p in secrets_outside)


@pytest.mark.parametrize("bad_name", BAD_FILENAMES)
def test_bad_filenames_are_rejected(client, secrets_outside, bad_name):
    token = csrf_token(client)
    room = room_of(client)
    for target_room in [room, "f" * 32]:
        response = client.get(f"/download/{target_room}/{bad_name}")
        assert response.status_code in (302, 404)
        assert b"TOP-SECRET" not in response.data
        response = client.post(f"/remove/{target_room}/{bad_name}", data={"csrf_token": token})
        assert response.status_code in (302, 403, 404, 405)
    assert all(p.exists() for p in secrets_outside)


# ---------- 3. 上傳與清單 ----------
def test_upload_shows_on_owner_and_share_page(client, config):
    response = upload(client, "我的 報告.txt", b"abc", follow=True)
    html = response.get_data(as_text=True)
    assert messages.upload_success("我的_報告.txt") in html
    assert "我的_報告.txt" in html

    room = room_of(client)
    share_html = client.get(f"/share_view/{room}").get_data(as_text=True)
    assert "我的_報告.txt" in share_html
    assert "3 bytes" in share_html


def test_same_name_twice_coexists(client, config):
    upload(client, "same.txt", b"one")
    upload(client, "same.txt", b"two")
    names = files_on_disk(config)
    assert len(names) == 2
    assert all(n.endswith("_same.txt") for n in names)
    assert client.get("/").get_data(as_text=True).count('title="same.txt"') == 2


def test_upload_without_file(client, config):
    token = csrf_token(client)
    response = client.post("/upload", data={"csrf_token": token}, follow_redirects=True)
    assert messages.NO_FILE_SELECTED in response.get_data(as_text=True)
    assert files_on_disk(config) == []


def test_upload_with_unusable_name(client, config):
    response = upload(client, "???", follow=True)
    assert messages.INVALID_FILENAME in response.get_data(as_text=True)
    assert files_on_disk(config) == []


def test_download(client):
    upload(client, "資料.txt", b"file-content")
    room = room_of(client)
    stored = next((client.application.config["QUICKSHARE"].upload_dir / room).iterdir()).name
    response = client.get(f"/download/{room}/{stored}")
    assert response.status_code == 200
    assert response.data == b"file-content"
    assert "attachment" in response.headers["Content-Disposition"]
    assert "%E8%B3%87%E6%96%99.txt" in response.headers["Content-Disposition"]  # 資料.txt
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_download_missing_file_redirects_to_share_page(client):
    room = room_of_new(client)
    response = client.get(f"/download/{room}/0123abcd_none.txt")
    assert response.status_code == 302
    assert response.headers["Location"].endswith(f"/share_view/{room}")
    html = client.get(response.headers["Location"]).get_data(as_text=True)
    assert messages.FILE_NOT_FOUND in html


def room_of_new(client):
    client.get("/")
    return room_of(client)


def test_long_name_is_shortened_with_full_title(client):
    long_name = "abcdefghijklmnopqrstuvwxyz0123456789.txt"
    html = upload(client, long_name, follow=True).get_data(as_text=True)
    assert f'title="{long_name}"' in html
    assert "abcdefghijkl...yz0123456789.txt" in html


# ---------- 4. 配額 ----------
def test_quota_keeps_newest(client, config):
    for i in range(1, 6):
        upload(client, f"f{i}.txt")
    html = client.get("/").get_data(as_text=True)
    for kept in ["f3.txt", "f4.txt", "f5.txt"]:
        assert f'title="{kept}"' in html
    for gone in ["f1.txt", "f2.txt"]:
        assert f'title="{gone}"' not in html
    assert len(files_on_disk(config)) == 3


def test_viewing_list_deletes_nothing(client, config):
    room = room_of_new(client)
    room_dir = config.upload_dir / room
    room_dir.mkdir(parents=True)
    for i in range(6):
        (room_dir / f"0000000{i}_f{i}.txt").write_text("x")
    client.get("/")
    client.get(f"/share_view/{room}")
    assert len(files_on_disk(config)) == 6


# ---------- 5. 權限 ----------
def test_other_session_cannot_delete(app, client, config):
    upload(client, "mine.txt")
    room = room_of(client)
    stored = files_on_disk(config)[0]

    intruder = app.test_client()
    token = csrf_token(intruder)
    response = intruder.post(f"/remove/{room}/{stored}", data={"csrf_token": token})
    assert response.status_code == 403
    assert files_on_disk(config) == [stored]


def test_share_page_has_no_upload_or_delete(client):
    upload(client, "mine.txt")
    room = room_of(client)
    html = client.get(f"/share_view/{room}").get_data(as_text=True)
    assert "Share Files" in html
    assert 'name="the_file"' not in html
    assert "/remove/" not in html
    assert "/download/" in html


def test_owner_can_delete(client, config):
    upload(client, "mine.txt")
    room = room_of(client)
    stored = files_on_disk(config)[0]
    token = csrf_token(client)
    response = client.post(f"/remove/{room}/{stored}", data={"csrf_token": token}, follow_redirects=True)
    assert messages.DELETE_SUCCESS in response.get_data(as_text=True)
    assert files_on_disk(config) == []

    response = client.post(f"/remove/{room}/{stored}", data={"csrf_token": token}, follow_redirects=True)
    assert messages.FILE_NOT_FOUND in response.get_data(as_text=True)


# ---------- 6. CSRF ----------
def test_upload_without_csrf_is_rejected(client, config):
    client.get("/")
    response = client.post(
        "/upload",
        data={"the_file": (io.BytesIO(b"x"), "a.txt")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 302
    assert files_on_disk(config) == []
    html = client.get("/").get_data(as_text=True)
    assert messages.PAGE_EXPIRED in html


def test_remove_without_csrf_is_rejected(client, config):
    upload(client, "a.txt")
    room = room_of(client)
    stored = files_on_disk(config)[0]
    response = client.post(f"/remove/{room}/{stored}", follow_redirects=True)
    assert messages.PAGE_EXPIRED in response.get_data(as_text=True)
    assert files_on_disk(config) == [stored]


def test_get_remove_is_405(client):
    room = room_of_new(client)
    assert client.get(f"/remove/{room}/0123abcd_a.txt").status_code == 405


# ---------- 7. 413 ----------
def test_upload_over_request_limit(client, config):
    # 設定上限 1 MB，MAX_CONTENT_LENGTH 為 2 MB；3 MB 會被 Flask 直接擋下
    response = upload(client, "big.bin", b"x" * (3 * 1024 * 1024), follow=True)
    assert messages.file_too_large(1) in response.get_data(as_text=True)
    assert files_on_disk(config) == []


def test_upload_over_file_limit(client, config):
    # 1.5 MB 通過 MAX_CONTENT_LENGTH，但 save_file 會拒絕，且不留下暫存檔
    response = upload(client, "big.bin", b"x" * (1024 * 1024 + 512 * 1024), follow=True)
    assert messages.file_too_large(1) in response.get_data(as_text=True)
    assert files_on_disk(config) == []


def test_upload_exactly_at_limit(client, config):
    upload(client, "ok.bin", b"x" * (1024 * 1024))
    assert len(files_on_disk(config)) == 1


# ---------- 9. 延遲建立 ----------
def test_index_does_not_create_folders(client, config):
    client.get("/")
    client.get("/")
    assert not config.upload_dir.exists() or list(config.upload_dir.iterdir()) == []


# ---------- 11. 分享頁 ----------
def test_share_view_for_unknown_room(client):
    response = client.get("/share_view/" + "e" * 32)
    assert response.status_code == 200
    assert messages.SHARE_EMPTY in response.get_data(as_text=True)


def test_owner_page_empty_message_and_limits(client):
    html = client.get("/").get_data(as_text=True)
    assert messages.OWNER_EMPTY in html
    assert messages.limits_notice(1, 3, 30) in html
    assert 'data-max-bytes="1048576"' in html


# ---------- QR code、反向代理、cookie ----------
def test_qrcode_png(client):
    room = room_of_new(client)
    response = client.get(f"/qrcode/{room}")
    assert response.status_code == 200
    assert response.mimetype == "image/png"
    assert response.data.startswith(b"\x89PNG")


def test_share_link_uses_https_behind_proxy(client):
    html = client.get("/", headers={"X-Forwarded-Proto": "https"}).get_data(as_text=True)
    assert 'value="https://localhost/share_view/' in html


def test_session_cookie_flags(client):
    cookie = client.get("/").headers["Set-Cookie"]
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie
    assert "Expires=" in cookie


# ---------- 錯誤處理與 logging ----------
def test_404_page_and_log(client, config):
    response = client.get("/no-such-page")
    assert response.status_code == 404
    assert messages.PAGE_NOT_FOUND in response.get_data(as_text=True)
    log = config.log_file.read_text(encoding="utf-8")
    assert "WARNING" in log and "/no-such-page" in log
    assert "Traceback" not in log


def test_500_page_and_log(app, config):
    def boom():
        raise RuntimeError("kaboom")
    app.add_url_rule("/boom", view_func=boom)
    app.config["PROPAGATE_EXCEPTIONS"] = False  # TESTING 模式預設會把例外直接拋給測試
    response = app.test_client().get("/boom")
    assert response.status_code == 500
    assert messages.SERVER_ERROR in response.get_data(as_text=True)
    log = config.log_file.read_text(encoding="utf-8")
    assert "Traceback" in log and "kaboom" in log


def test_upload_and_delete_are_logged(client, config):
    upload(client, "log.txt")
    room = room_of(client)
    stored = files_on_disk(config)[0]
    client.post(f"/remove/{room}/{stored}", data={"csrf_token": csrf_token(client)})
    log = config.log_file.read_text(encoding="utf-8")
    assert "上傳成功" in log and "刪除檔案" in log
