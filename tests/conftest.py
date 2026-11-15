import io
import re

import pytest

from app import create_app
from app.config import Config


@pytest.fixture
def config(tmp_path):
    return Config(
        secret_key="test-secret",
        max_upload_mb=1,
        max_files_per_room=3,
        upload_dir=tmp_path / "uploads",
        log_file=tmp_path / "logs" / "test.log",
        start_cleanup_thread=False,
    )


@pytest.fixture
def app(config):
    app = create_app(config)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def csrf_token(client):
    """開啟首頁並取出 CSRF token。"""
    html = client.get("/").get_data(as_text=True)
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


def room_of(client):
    with client.session_transaction() as sess:
        return sess["room_id"]


def upload(client, name, content=b"hello", follow=False):
    token = csrf_token(client)
    return client.post(
        "/upload",
        data={"csrf_token": token, "the_file": (io.BytesIO(content), name)},
        content_type="multipart/form-data",
        follow_redirects=follow,
    )
