"""錯誤處理與 logging。"""
import logging
from logging.handlers import RotatingFileHandler

from flask import flash, redirect, render_template, request, url_for
from flask_wtf.csrf import CSRFError
from werkzeug.exceptions import Forbidden, InternalServerError, NotFound, RequestEntityTooLarge

from . import messages

logger = logging.getLogger("quickshare")


def setup_logging(config):
    """把 quickshare logger 寫到輪替的 log 檔（1 MB × 3 份）。"""
    config.log_file.parent.mkdir(parents=True, exist_ok=True)
    # 重複建立 app（例如測試）時，先關掉舊的 handler，避免重複寫入
    for old in list(logger.handlers):
        logger.removeHandler(old)
        old.close()
    handler = RotatingFileHandler(config.log_file, maxBytes=1024 * 1024, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def register_error_handlers(app):
    max_mb = app.config["QUICKSHARE"].max_upload_mb

    @app.errorhandler(NotFound)
    def not_found(error):
        logger.warning("404 找不到：%s", request.path)
        return render_template("error.html", message=messages.PAGE_NOT_FOUND), 404

    @app.errorhandler(Forbidden)
    def forbidden(error):
        logger.warning("403 沒有權限：%s", request.path)
        return render_template("error.html", message=messages.NO_PERMISSION), 403

    @app.errorhandler(RequestEntityTooLarge)
    def too_large(error):
        flash(messages.file_too_large(max_mb), "warning")
        return redirect(url_for("main.index"))

    @app.errorhandler(CSRFError)
    def csrf_error(error):
        flash(messages.PAGE_EXPIRED, "warning")
        return redirect(url_for("main.index"))

    @app.errorhandler(InternalServerError)
    def server_error(error):
        original = getattr(error, "original_exception", None) or error
        logger.exception("500 伺服器錯誤：%s", request.path, exc_info=original)
        return render_template("error.html", message=messages.SERVER_ERROR), 500
