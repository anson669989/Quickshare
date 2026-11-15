"""所有顯示給使用者的中文訊息集中在這裡，方便修改用字。"""

NO_FILE_SELECTED = "沒有選擇檔案"
INVALID_FILENAME = "該檔名無法被上傳"
FILE_NOT_FOUND = "檔案不存在，可能已被刪除或過期"
DELETE_SUCCESS = "檔案已刪除"
NO_PERMISSION = "沒有權限執行這個操作"
PAGE_EXPIRED = "頁面已過期，請重新操作"
SHARE_EMPTY = "此分享連結沒有檔案，或已過期"
OWNER_EMPTY = "尚無檔案"
PAGE_NOT_FOUND = "找不到頁面"
SERVER_ERROR = "伺服器發生錯誤，請稍後再試"

# 以下給前端 JS 使用（經由 data-* 屬性傳入）；{name}、{done}、{total} 由 JS 代入
UPLOAD_PROGRESS = "上傳中… {done}/{total}"
UPLOAD_FAILED = "{name}：上傳失敗，請稍後再試"
COPY_DONE = "已複製"
COPY_MANUAL = "無法自動複製，連結已選取，請長按連結手動複製"


def upload_success(filename):
    return f"上傳成功：{filename}"


def file_too_large(max_mb):
    return f"檔案太大了！上傳限制為 {max_mb} MB"


def upload_skipped_too_large(max_mb):
    """前端略過太大的檔案時顯示（{name} 由 JS 代入）。"""
    return "{name}：檔案太大，已略過（上限 " + str(max_mb) + " MB）"


def info_lines(max_mb, max_files, ttl_days):
    """說明彈窗的內容，一行一項。"""
    return [
        "本網站為私人伺服器，不定時開啟。",
        f"單檔大小限制為 {max_mb} MB。",
        f"每個房間最多保留 {max_files} 個檔案，超過時自動刪除最舊的。",
        f"{ttl_days} 天未上傳新檔案，房間將自動清除。",
    ]
