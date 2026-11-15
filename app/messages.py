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


def upload_success(filename):
    return f"上傳成功：{filename}"


def file_too_large(max_mb):
    return f"檔案太大了！上傳限制為 {max_mb} MB"


def limits_notice(max_mb, max_files, ttl_days):
    return f"單檔上限 {max_mb} MB · 最多保留 {max_files} 個檔案 · {ttl_days} 天未上傳新檔案將自動清除"


def info_text(max_mb):
    return f"本網站為私人伺服器，不定時開啟；單檔大小限制為 {max_mb} MB。"
