# Quick Share

架在個人 Windows 電腦上的檔案快傳網站。開啟首頁就會得到自己的「房間」，點擊上傳框選檔（可多選）或把多個檔案拖進上傳框即自動上傳，再把分享連結（或 QR code）給別人下載。

- 多個檔案會一個一個依序上傳（每個檔案各自一次請求，不會因為總和超過上限而失敗），上傳時顯示進度，傳完後列出每個檔案的結果。
- 每個房間最多保留 10 個檔案（超過時刪除最舊的），30 天沒有新上傳就整個房間刪除。這些限制可在標題旁的說明圖示中看到。
- 房間 ID 是 10 碼小寫英數，也就是分享連結最後一段；舊版留下的 32 碼 ID 會自動換發新房間。
- 不使用資料庫，檔案都放在 `uploads/`。

## 安裝

需要 Python 3.12。在專案資料夾開啟命令提示字元：

```bat
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

要跑測試的話再安裝：

```bat
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

## 設定

1. 把 `.env.example` 複製成 `.env`。
2. 產生一組密鑰，貼到 `.env` 的 `SECRET_KEY=` 後面：

   ```bat
   .venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
   ```

3. 其他設定（上傳上限、保留檔案數、天數、連接埠……）都在 `.env`，每一項都有註解。改完後重新啟動才會生效。

注意：

- `.env` 含有密鑰，**不要**放進 git（已列在 `.gitignore`）。
- 經 Cloudflare 以 https 對外時，請把 `SESSION_COOKIE_SECURE` 設為 `true`；只在本機用 `http://` 測試時要維持 `false`，否則會一直顯示「頁面已過期」。
- 設定有誤（例如缺少 `SECRET_KEY`、數字填錯）時，程式會印出是哪一個變數有問題並結束。

## 啟動

雙擊 `run.bat`，或在命令提示字元執行：

```bat
.venv\Scripts\python.exe run.py
```

看到「Quick Share 已啟動」後，用瀏覽器開啟 `http://127.0.0.1:5000/`。按 Ctrl+C 結束。

如果顯示「已經有其他程式在使用」，代表同一個連接埠已有程式（例如舊版網站）在執行，請先關閉它或修改 `.env` 的 `PORT`。

紀錄檔在 `logs/quickshare.log`。

## 測試

```bat
.venv\Scripts\python.exe -m pytest
```

## 檔案說明

| 檔案 | 說明 |
| --- | --- |
| `run.py` / `run.bat` | 讀設定、建立 app、用 waitress 啟動 |
| `app/config.py` | 讀取 `.env` 並檢查設定 |
| `app/storage.py` | 所有檔案操作（上傳、清單、刪除、過期清理、路徑安全檢查） |
| `app/views.py` | 網址路由 |
| `app/errors.py` | 錯誤頁面與 log |
| `app/messages.py` | 所有中文訊息，要改用字改這裡 |
| `app/templates/` | 網頁模板 |
| `app/static/` | CSS、JavaScript、圖示 |
| `tests/` | 自動測試 |
