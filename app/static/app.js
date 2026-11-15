// Quick Share 前端行為（原生 JS，不用 inline onclick）
"use strict";

document.addEventListener("DOMContentLoaded", function () {
  // ---------- 上傳：選擇檔案後檢查大小並自動送出 ----------
  const form = document.querySelector(".js-upload-form");
  if (form) {
    const input = form.querySelector(".js-upload-input");
    const text = form.querySelector(".js-upload-text");
    let uploading = false;

    input.addEventListener("change", function () {
      const file = input.files[0];
      if (!file || uploading) {
        return;
      }
      // 上限由模板的 data-max-bytes 傳入
      if (file.size > Number(form.dataset.maxBytes)) {
        showFlash(form.dataset.tooLargeMessage, "warning");
        input.value = "";
        return;
      }
      uploading = true;
      form.classList.add("is-uploading");
      text.textContent = form.dataset.uploadingText;
      form.submit();
    });

    // 從瀏覽器「上一頁」回來時，把上傳區恢復成可用狀態
    const originalText = text.textContent;
    window.addEventListener("pageshow", function (event) {
      if (event.persisted) {
        uploading = false;
        form.classList.remove("is-uploading");
        text.textContent = originalText;
        input.value = "";
      }
    });
  }

  // ---------- 彈窗：開啟與關閉 ----------
  document.querySelectorAll(".js-open-dialog").forEach(function (button) {
    button.addEventListener("click", function () {
      const dialog = document.querySelector("." + button.dataset.dialog);
      if (dialog) {
        dialog.showModal();
      }
    });
  });

  document.querySelectorAll(".dialog").forEach(function (dialog) {
    // 點彈窗外的灰色背景也可以關閉
    dialog.addEventListener("click", function (event) {
      if (event.target === dialog) {
        dialog.close();
      }
    });
    dialog.querySelectorAll(".js-close-dialog").forEach(function (button) {
      button.addEventListener("click", function () {
        dialog.close();
      });
    });
  });

  // ---------- 複製分享連結 ----------
  const copyButton = document.querySelector(".js-copy");
  if (copyButton) {
    const linkInput = document.querySelector(".js-share-link");
    const status = document.querySelector(".js-copy-status");
    let timer = null;

    copyButton.addEventListener("click", function () {
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(linkInput.value).then(function () {
          status.textContent = copyButton.dataset.copiedText;
          clearTimeout(timer);
          timer = setTimeout(function () {
            status.textContent = "";
          }, 2000);
        }, function () {
          selectLink(linkInput);
        });
      } else {
        // 無法使用剪貼簿時（例如非 https），改為選取文字讓使用者自行複製
        selectLink(linkInput);
      }
    });
  }
});

function selectLink(input) {
  input.focus();
  input.select();
}

function showFlash(message, category) {
  const list = document.querySelector(".js-flash-list");
  if (!list) {
    return;
  }
  const item = document.createElement("div");
  item.className = "flash flash-" + category;
  item.textContent = message;
  list.replaceChildren(item);
}
