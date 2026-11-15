"""全部路由（一個 Blueprint）。路由不自行組合檔案路徑，一律呼叫 storage。"""
import io
import logging

import qrcode
from flask import (Blueprint, abort, current_app, flash, redirect, render_template,
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
        max_upload_mb=config.max_upload_mb,
        max_upload_bytes=config.max_upload_mb * 1024 * 1024,
        too_large_message=messages.file_too_large(config.max_upload_mb),
        limits_notice=messages.limits_notice(config.max_upload_mb, config.max_files_per_room, config.room_ttl_days),
        info_text=messages.info_text(config.max_upload_mb),
    )


@bp.get("/")
def index():
    return render_page(owner_room(), is_owner=True)


@bp.post("/upload")
def upload():
    room_id = owner_room()
    the_file = request.files.get("the_file")
    if the_file is None or not the_file.filename:
        flash(messages.NO_FILE_SELECTED, "warning")
        return redirect(url_for("main.index"))
    try:
        stored_name = get_storage().save_file(room_id, the_file)
    except InvalidFilename:
        flash(messages.INVALID_FILENAME, "error")
    except FileTooLarge:
        flash(messages.file_too_large(current_app.config["QUICKSHARE"].max_upload_mb), "warning")
    else:
        logger.info("上傳成功：%s/%s", room_id, stored_name)
        flash(messages.upload_success(storage.display_name(stored_name)), "success")
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
