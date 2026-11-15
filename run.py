"""讀取設定、建立 app，並用 waitress 啟動。"""
import socket
import sys

from waitress import serve

from app import create_app
from app.config import ConfigError, load_config


def port_in_use(host, port):
    """檢查是否已有程式在監聽這個連接埠。
    waitress 在 Windows 上不會因為連接埠被占用而報錯，請求可能被舊程式接走，所以先自己檢查。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        return sock.connect_ex((host, port)) == 0


def main():
    try:
        config = load_config()
    except ConfigError as error:
        print(f"[設定錯誤] {error}", file=sys.stderr)
        sys.exit(1)

    if port_in_use(config.host, config.port):
        print(f"[啟動失敗] {config.host}:{config.port} 已經有其他程式在使用，"
              "請先關閉它，或在 .env 修改 PORT。", file=sys.stderr)
        sys.exit(1)

    app = create_app(config)
    print(f"Quick Share 已啟動：http://{config.host}:{config.port}/  （按 Ctrl+C 結束）")
    # waitress 預設會刪掉 X-Forwarded-* 標頭；關掉這個行為，交給 app 裡的 ProxyFix 處理，
    # Cloudflare 傳來的 X-Forwarded-Proto 才能讓分享連結變成 https://
    serve(app, host=config.host, port=config.port, threads=config.threads,
          clear_untrusted_proxy_headers=False)


if __name__ == "__main__":
    main()
