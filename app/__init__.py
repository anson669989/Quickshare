"""Quick Share：application factory。"""
import logging
import threading
import time
from datetime import timedelta

from flask import Flask
from flask_wtf.csrf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix

from . import errors, storage
from .views import bp

logger = logging.getLogger("quickshare")
csrf = CSRFProtect()

CLEANUP_INTERVAL_SECONDS = 60 * 60  # 每小時清理一次過期房間


def run_cleanup(store):
    """執行一次過期清理；例外寫入 log，不往外拋（避免背景 thread 結束）。"""
    try:
        store.purge_expired_rooms()
    except Exception:
        logger.exception("過期清理失敗")


def cleanup_loop(store):
    while True:
        time.sleep(CLEANUP_INTERVAL_SECONDS)
        run_cleanup(store)


def create_app(config):
    app = Flask(__name__)
    app.config.update(
        QUICKSHARE=config,
        SECRET_KEY=config.secret_key,
        # 多留 1 MB 給 multipart 表頭
        MAX_CONTENT_LENGTH=(config.max_upload_mb + 1) * 1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=config.session_cookie_secure,
        PERMANENT_SESSION_LIFETIME=timedelta(days=config.owner_session_days),
        WTF_CSRF_TIME_LIMIT=None,
    )
    # 前面是 Cloudflare：信任一層 X-Forwarded-Proto，讓分享連結產生 https://
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1)

    csrf.init_app(app)
    errors.setup_logging(config)
    errors.register_error_handlers(app)

    store = storage.Storage(config)
    app.extensions["quickshare_storage"] = store

    app.jinja_env.filters["filesize"] = storage.format_size
    app.jinja_env.filters["shorten"] = lambda name: storage.shorten_name(name, config.display_name_limit)

    app.register_blueprint(bp)

    # 啟動時清理一次，之後由背景 thread 每小時清理
    run_cleanup(store)
    if config.start_cleanup_thread:
        threading.Thread(target=cleanup_loop, args=(store,), daemon=True).start()
    return app
