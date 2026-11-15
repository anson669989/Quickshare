"""全部路由（一個 Blueprint）。路由不自行組合檔案路徑，一律呼叫 storage。"""
import io
import logging

import qrcode
from flask import (Blueprint, abort, current_app, flash, jsonify, redirect, render_template,
                   request, send_file, session, url_for)

from . import messages, storage
from .storage import FileTooLarge, InvalidFilename

logger = logging.getLogger("quickshare")
bp = Blueprint("main", __name__)


def get_storage():
    return current_app.extensions["quickshare_storage"]


def owner_room():
    """取得目前 session 的房間 ID；沒有就產生一個（此時不建立資料夾）。"""
    room_id = session.get("room_id")
    if not storage.is_valid_room_id(room_id):
        room_id = storage.new_room_id()
        session["room_id"] = room_id
    session.permanent = True  # 每次造訪都會續期 cookie
    return room_id


def require_valid_room(room_id):
    if not storage.is_valid_room_id(room_id):
        abort(404)


def render_page(room_id, is_owner):
    config = current_app.config["QUICKSHARE"]
    return render_template(
        "index.html",
        is_owner=is_owner,
        room_id=room_id,
        files=get_storage().list_files(room_id),
        empty_message=messages.OWNER_EMPTY if is_owner else messages.SHARE_EMPTY,
        share_url=url_for("main.share_view", room_id=room_id, _external=True),
        max_upload_bytes=config.max_upload_mb * 1024 * 1024,
        info_lines=messages.info_lines(config.max_upload_mb, config.max_files_per_room, config.room_ttl_days),
        msg=messages,
        skipped_message=messages.upload_skipped_too_large(config.max_upload_mb),
    )


@bp.get("/")
def index():
    return render_page(owner_room(), is_owner=True)


def wants_json():
    """前端 JS（fetch）送來的請求會帶這個標頭，此時回傳 JSON 而不是轉址。"""
    return request.headers.get("X-Requested-With") == "fetch"


def save_one(room_id, the_file):
    """儲存一個上傳檔案，回傳 (類別, 訊息)。"""
    try:
        stored_name = get_storage().save_file(room_id, the_file)
    except InvalidFilename:
        return "error", messages.INVALID_FILENAME
    except FileTooLarge:
        return "warning", messages.file_too_large(current_app.config["QUICKSHARE"].max_upload_mb)
    logger.info("上傳成功：%s/%s", room_id, stored_name)
    return "success", messages.upload_success(storage.display_name(stored_name))


@bp.post("/upload")
def upload():
    """前端 JS 每次只送一個檔案並取得 JSON；沒有 JS 時以一般表單送出，結果用 flash 顯示。"""
    room_id = owner_room()
    files = [f for f in request.files.getlist("the_file") if f.filename]
    if not files:
        results = [("warning", messages.NO_FILE_SELECTED)]
    else:
        results = [save_one(room_id, f) for f in files]

    if wants_json():
        category, message = results[0]
        return jsonify(category=category, message=message)
    for category, message in results:
        flash(message, category)
    return redirect(url_for("main.index"))


@bp.get("/share_view/<room_id>")
def share_view(room_id):
    require_valid_room(room_id)
    return render_page(room_id, is_owner=False)


@bp.get("/qrcode/<room_id>")
def qrcode_image(room_id):
    require_valid_room(room_id)
    share_url = url_for("main.share_view", room_id=room_id, _external=True)
    buffer = io.BytesIO()
    qrcode.make(share_url, box_size=8, border=2).save(buffer)
    buffer.seek(0)
    return send_file(buffer, mimetype="image/png")


@bp.get("/download/<room_id>/<filename>")
def download(room_id, filename):
    require_valid_room(room_id)
    path = get_storage().get_file(room_id, filename)
    if path is None:
        flash(messages.FILE_NOT_FOUND, "warning")
        return redirect(url_for("main.share_view", room_id=room_id))
    response = send_file(path, as_attachment=True, download_name=storage.display_name(filename))
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@bp.post("/remove/<room_id>/<filename>")
def remove(room_id, filename):
    if session.get("room_id") != room_id or not storage.is_valid_room_id(room_id):
        abort(403)
    if get_storage().delete_file(room_id, filename):
        logger.info("刪除檔案：%s/%s", room_id, filename)
        flash(messages.DELETE_SUCCESS, "success")
    else:
        flash(messages.FILE_NOT_FOUND, "error")
    return redirect(url_for("main.index"))
