# Quick Share — 實作規格書（給 Claude Code）

> 這是一個**全新專案**，從零實作，不需要相容任何舊程式碼、舊檔名格式或舊連結。
> 使用者不是程式專家：程式碼請保持簡單好讀，回報進度與提問請用**繁體中文**。

---

## 1. 產品說明

Quick Share 是架在個人 Windows 電腦上的檔案快傳網站，經由 Cloudflare 以 https 對外（Cloudflare 單檔上限 100 MB）。

### 使用流程

1. 使用者開啟 `/`，取得自己的「房間」（以 session cookie 記住，使用者看不到帳號密碼）。
2. 使用者選擇檔案後自動上傳（一次一個檔案）。
3. 點「Share file」→ 彈窗顯示分享連結與 QR code，並可一鍵複製連結。
4. 其他人開啟分享連結 → 只能看清單與下載，不能上傳或刪除。
5. 擁有者可以刪除自己房間的檔案。
6. 每個房間最多保留 N 個檔案，超過時自動刪除最舊的。
7. 房間超過 30 天沒有新上傳，整個房間自動刪除。

### 不做的事

- 不做帳號、密碼、永久房間或任何特定 ID 的豁免。
- 不使用資料庫；所有狀態都在檔案系統與 session cookie。
- 不引入前端框架或建置工具。

---

## 2. 技術選擇

- Python 3.12、Flask、waitress（正式啟動）、python-dotenv、`qrcode[pil]`、Flask-WTF（只用 `CSRFProtect`）。
- 測試：pytest。
- `requirements.txt` 請列出以上全部，版本釘在安裝當下的最新穩定版；pytest 放 `requirements-dev.txt`。
- 前端：一個 Jinja 模板、一份 CSS、一份原生 JS。

---

## 3. 目錄結構

```
quick-share/
├─ run.py                 # 讀設定、建立 app、用 waitress 啟動
├─ run.bat                # .venv\Scripts\python.exe run.py
├─ requirements.txt
├─ requirements-dev.txt
├─ .env.example
├─ .gitignore             # .env、.venv/、uploads/、logs/、__pycache__/、.pytest_cache/
├─ README.md              # 繁體中文：安裝、設定、啟動、測試
├─ app/
│  ├─ __init__.py         # create_app(config)：application factory
│  ├─ config.py           # Config dataclass，從 .env 讀取，含預設值與驗證
│  ├─ storage.py          # 唯一碰檔案系統的模組
│  ├─ views.py            # 全部路由（一個 Blueprint）
│  ├─ errors.py           # 錯誤處理與 logging
│  ├─ messages.py         # 所有中文使用者訊息
│  ├─ templates/index.html
│  ├─ templates/error.html
│  └─ static/style.css、app.js、icon/
└─ tests/
```

檔案數量刻意保持少：這個專案的後端約 300 行，不要再細拆。

---

## 4. 設定（`.env`）

| 變數                        | 預設值                     | 說明                                                                   |
| --------------------------- | -------------------------- | ---------------------------------------------------------------------- |
| `SECRET_KEY`                | 無（必填）                 | 缺少時啟動失敗，並印出清楚的中文錯誤訊息                               |
| `MAX_UPLOAD_MB`             | `100`                      | 單檔上限                                                               |
| `MAX_FILES_PER_ROOM`        | `10`                       | 每個房間保留的檔案數                                                   |
| `ROOM_TTL_DAYS`             | `30`                       | 房間多久沒有新上傳就刪除                                               |
| `OWNER_SESSION_DAYS`        | `30`                       | 擁有者 cookie 有效天數（每次造訪續期）                                 |
| `DISPLAY_NAME_LIMIT`        | `12`                       | 顯示檔名時前後各保留的字數                                             |
| `UPLOAD_DIR`                | `uploads`                  | 相對路徑以**專案根目錄**為基準（用 `Path(__file__)` 推算，不依賴 CWD） |
| `LOG_FILE`                  | `logs/quickshare.log`      | 同上                                                                   |
| `HOST` / `PORT` / `THREADS` | `127.0.0.1` / `5000` / `4` | waitress 參數                                                          |
| `SESSION_COOKIE_SECURE`     | `false`                    | 正式環境建議設為 `true`；本機用 http 測試時需為 `false`                |

要求：

- 數值型設定無法轉型或小於 1 時，啟動失敗並說明是哪一個變數。
- `.env.example` 列出全部變數與註解，`SECRET_KEY` 留空並註明產生方式（`python -c "import secrets; print(secrets.token_hex(32))"`）。**不可**寫入任何真實密鑰。
- `create_app(config)` 接受 Config 物件，方便測試時指向 `tmp_path`。

---

## 5. 路由

| 路徑                             | Method | 說明                               | 權限                             |
| -------------------------------- | ------ | ---------------------------------- | -------------------------------- |
| `/`                              | GET    | 擁有者頁面                         | session                          |
| `/upload`                        | POST   | 表單欄位 `the_file`，需 CSRF token | session                          |
| `/share_view/<room_id>`          | GET    | 唯讀分享頁                         | 任何人                           |
| `/qrcode/<room_id>`              | GET    | 分享連結的 QR code（PNG）          | 任何人                           |
| `/download/<room_id>/<filename>` | GET    | 下載                               | 任何人                           |
| `/remove/<room_id>/<filename>`   | POST   | 刪除，需 CSRF token                | session 的房間必須等於 `room_id` |

行為細節：

- `/`：session 沒有房間時產生新 ID 存入 session，**但不建立資料夾**（第一次上傳時才建立，避免爬蟲製造大量空資料夾）。
- 分享連結由後端以 `url_for(..., _external=True)` 產生並直接渲染進模板，不需要另外的 API。
- `/share_view/<room_id>`：ID 格式不合 → 404；格式正確但房間不存在或為空 → 正常顯示頁面與「此分享連結沒有檔案，或已過期」訊息。
- `/download`：檔案不存在 → flash 訊息後導回該房間的分享頁。以附件方式回傳，下載檔名為原始檔名（去掉 uid 前綴），並加上 `X-Content-Type-Options: nosniff`。
- `/remove`：session 房間不符 → 403；成功與失敗都要有 flash 訊息，之後導回 `/`。
- 路由函式**不可**自行組合檔案路徑，一律呼叫 `storage.py`。

---

## 6. 儲存層（`storage.py`）

### 房間 ID

- 以 `secrets.token_hex(16)` 產生（32 碼小寫 hex）。不可用 `token_urlsafe`：Windows 檔案系統不分大小寫，會讓不同 ID 指向同一資料夾。
- 所有接受 `room_id` 的函式先以 `^[0-9a-f]{32}$` 驗證，不合即拋出自訂例外。

### 檔名

- 儲存名格式：`<uid>_<安全檔名>`，`uid` 為 `secrets.token_hex(4)`（8 碼 hex）。
- 顯示名與下載名：取第一個 `_` 之後的部分。
- 合法儲存名的格式：`^[0-9a-f]{8}_[一-鿿A-Za-z0-9._-]+$`；不合者一律視為不存在。
- 安全檔名的產生規則：
  1. 同時以 `/` 與 `\` 切割，只取最後一段。
  2. Unicode 正規化為 NFC。
  3. 空白轉成 `_`。
  4. 只保留中文（`一-鿿`）、英數、`.`、`_`、`-`。
  5. 去掉開頭與結尾的 `.`。
  6. 長度上限 150 字元（超過時截斷主檔名、保留副檔名）。
  7. 結果為空 → **`raise`** 自訂例外，路由顯示「該檔名無法被上傳」。

### 路徑安全

- 提供單一內部函式，把 `(room_id, stored_name)` 轉成路徑：先做上述格式驗證，再 `resolve()` 並確認 `is_relative_to(upload_dir / room_id)`。所有讀、寫、刪都經過它。

### 操作

- `list_files(room_id)`：回傳依修改時間新到舊排序的清單（儲存名、顯示名、大小、時間）。**純讀取，不刪除任何東西**。房間不存在回傳空清單。忽略不符合儲存名格式的項目（包含上傳中的暫存檔）。
- `save_file(room_id, upload)`：建立房間資料夾 → 寫入暫存檔 `<uid>.part` → 完成後 `os.replace` 成正式檔名 → 執行配額清理（只保留最新的 `MAX_FILES_PER_ROOM` 個）。失敗時刪除暫存檔。
- `delete_file(room_id, stored_name)`：回傳是否成功刪除。
- `purge_expired_rooms()`：掃描 `UPLOAD_DIR` 下**名稱符合房間 ID 格式**的資料夾；最後活動時間（最新檔案的修改時間，空房間則用資料夾修改時間）超過 `ROOM_TTL_DAYS` 就整個刪除。其他名稱的檔案或資料夾一律不碰。
- 檔案大小格式化（bytes / kB / MB）放在這裡或做成 Jinja filter 皆可。

### 過期清理的執行時機

- app 啟動時執行一次，之後由背景 daemon thread 每小時執行一次。清理過程中的例外要寫入 log，不可讓 thread 結束。測試時可關閉背景 thread。

---

## 7. 安全性要求

1. **路徑穿越**：`room_id` 與 `filename` 含 `..`、`/`、`\`、`%5C`、`%2F` 等任何變形時，都不可讀取、列出或刪除房間資料夾以外的東西。這是在 Windows 上執行，`\` 是路徑分隔符，請特別測試。
2. **CSRF**：使用 Flask-WTF 的 `CSRFProtect`；上傳與刪除表單都帶 token。`WTF_CSRF_TIME_LIMIT = None`（跟隨 session）。CSRF 驗證失敗 → flash「頁面已過期，請重新操作」並導回 `/`。
3. **Session cookie**：`HttpOnly`、`SameSite=Lax`、`session.permanent = True`、有效期 `OWNER_SESSION_DAYS`。
4. **反向代理**：waitress 只綁 `127.0.0.1`，前面是 Cloudflare。套用 `ProxyFix(x_proto=1)`，讓分享連結與 QR code 產生 `https://` 網址。
5. **上傳大小**：`MAX_CONTENT_LENGTH` 設為 `MAX_UPLOAD_MB` MB 再加 1 MB（留給 multipart 表頭）；`save_file` 另外確認檔案本體不超過 `MAX_UPLOAD_MB`。
6. 模板一律使用 Jinja 自動跳脫，不可用 `|safe` 輸出使用者提供的內容。

---

## 8. 錯誤處理與 logging

- 使用 `RotatingFileHandler`（1 MB × 3 份），格式含時間、等級、訊息。
- 404：寫一行 WARNING（含路徑），**不寫 traceback**；顯示 `error.html`（簡短訊息加回首頁連結）。
- 413：flash「檔案太大了！上傳限制為 N MB」（N 取自設定）並導回 `/`。
- 500：以 `logger.exception` 記錄完整 traceback；顯示 `error.html`。
- 不可用 `try/finally: return` 或空的 `except` 吞掉例外。
- 上傳成功、刪除、過期清理各寫一行 INFO。

---

## 9. 前端

### 頁面

- `index.html` 由擁有者頁與分享頁共用，以 `is_owner` 切換。介面語言為繁體中文，`<html lang="zh-Hant">`。
- 擁有者頁：標題「Quick Share」、說明按鈕（彈窗）、上傳區、「Share file」按鈕、檔案清單。
- 分享頁：標題「Share Files」、回首頁連結、檔案清單（只有下載按鈕）。
- 說明彈窗內容：本網站為私人伺服器，不定時開啟；單檔大小限制為 N MB。
- 分享彈窗：QR code 圖片、唯讀的連結輸入框、「複製」按鈕。複製成功時在按鈕旁顯示「已複製」，不使用 `alert()`；`navigator.clipboard` 不可用時改為選取輸入框文字。
- **上傳限制公告**：在上傳區下方以灰色小字顯示一行，例如「單檔上限 100 MB · 最多保留 10 個檔案 · 30 天未上傳新檔案將自動清除」，數字全部由後端傳入。
- **檔案清單區保留展示空間**：設定 `min-height`，沒有檔案時顯示「尚無檔案」，版面不會因為清單為空而塌陷。
- 每個檔案顯示：顯示名（過長時中間以 `...` 省略，前後各保留 `DISPLAY_NAME_LIMIT` 字並保留副檔名；完整檔名放在 `title` 屬性）、大小、下載按鈕、刪除按鈕（僅擁有者，為 POST 表單內的 `<button>`）。
- 檔名省略與大小格式化註冊為 Jinja filter。

### 行為（`app.js`）

- 選擇檔案後先檢查大小：超過上限 → 顯示警告訊息並清空選擇，不送出；否則自動送出表單，並把上傳區切換成「上傳中…」狀態避免重複送出。
- 上限等數值以 `data-*` 屬性從模板傳給 JS，JS 與模板中不可寫死 100。
- 不使用 inline `onclick`，事件以 `addEventListener` 綁定。

### 樣式（`style.css`）

- 單一檔案，不用 `@import`。只用 class 選擇器；HTML 中不可有重複的 id。
- flash 訊息依 category 顯示不同樣式：`success`、`warning`、`error`。
- 手機與桌面都要好用；不要停用縮放（不加 `user-scalable=no`）。
- 風格：簡潔、置中的單欄面板。

### 圖示

- 開始實作前先問使用者：是否要沿用舊專案的 `static/icon/` 圖示（favicon、上傳、下載、垃圾桶、首頁、說明圖示與裝飾圖）。
- 使用者提供 → 放進 `app/static/icon/` 並使用。未提供 → 以 inline SVG 圖示代替，favicon 用簡單的 SVG。

---

## 10. 訊息集中管理（`messages.py`）

所有顯示給使用者的中文字串放在這個模組，路由與錯誤處理只引用常數或函式。至少包含：沒有選擇檔案、檔名無法上傳、上傳成功（含檔名）、檔案太大（含上限）、檔案不存在、刪除成功、沒有權限、頁面已過期、分享連結沒有檔案或已過期、找不到頁面、伺服器錯誤。

---

## 11. 測試（pytest，Flask test client + `tmp_path`）

1. **檔名清理**：中文保留、空白轉底線、路徑成分被去除（`a/b.txt`、`a\b.txt`、`..\..\x`）、全為非法字元時拋出例外、過長時截斷並保留副檔名。
2. **路徑穿越**：對 `/download`、`/remove`、`/share_view`、`/qrcode` 送出含 `..`、`\`、`%5C`、`%2F`、非 hex、長度錯誤的 `room_id` 與 `filename`，確認回應為 404 或拒絕，且房間外預先放置的檔案仍然存在。
3. **上傳與清單**：上傳後出現在擁有者頁與分享頁；顯示名正確；同名檔案上傳兩次會並存。
4. **配額**：上傳超過 `MAX_FILES_PER_ROOM` 個後只剩最新的 N 個；單純開啟清單頁不會刪除任何檔案。
5. **權限**：另一個 session 無法刪除別人房間的檔案（403）；分享頁沒有上傳表單與刪除按鈕。
6. **CSRF**：沒有 token 的 `/upload` 與 `/remove` 被拒絕；`GET /remove/...` 回傳 405。
7. **413**：超過上限的上傳得到警告訊息，且沒有留下檔案或暫存檔。
8. **過期清理**：把房間內檔案的修改時間改成 31 天前，執行 `purge_expired_rooms()` 後房間被刪除；未過期的房間與名稱不符合格式的資料夾不受影響。
9. **延遲建立**：只開啟 `/` 不會在 `UPLOAD_DIR` 產生資料夾。
10. **設定**：缺少 `SECRET_KEY` 或數值非法時，載入設定會失敗並帶有變數名稱。
11. **分享頁**：格式正確但不存在的房間回傳 200 並顯示提示訊息。

---

## 12. 工作順序與驗收

建議順序：`config.py` → `storage.py` 與其測試 → 路由與錯誤處理 → 模板、CSS、JS → 其餘測試 → README 與周邊檔案。

完成條件：

- `pytest` 全數通過。
- 在 Windows 上以 `run.bat` 啟動後，手動走過一次：上傳、清單、分享彈窗與 QR code、另開無痕視窗開分享連結下載、刪除、上傳超過上限的檔案。
- `git init` 並完成第一次 commit；**不要**自行 push 或建立遠端 repo，等使用者指示。
- 最後以繁體中文回報：目錄結構、如何啟動、如何修改設定、有哪些地方與本規格不同以及原因。

遇到規格沒寫到的小決定，選最簡單的做法並在最後回報即可；會影響使用者行為的決定（例如介面文字以外的功能增減）請先詢問。
