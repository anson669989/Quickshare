// Quick Share 前端行為（原生 JS，不用 inline onclick）
"use strict";

document.addEventListener("DOMContentLoaded", function () {
  setupUpload();
  setupDialogs();
  setupCopy();
});

// ---------- 上傳：點擊選檔或拖曳，可多檔，每個檔案各自送一次請求 ----------
function setupUpload() {
  const form = document.querySelector(".js-upload-form");
  if (!form) {
    return;
  }
  const input = form.querySelector(".js-upload-input");
  const zone = form.querySelector(".js-upload-zone");
  const text = form.querySelector(".js-upload-text");
  const originalText = text.textContent;
  let uploading = false;

  // 點擊選檔與拖曳都走這一段
  async function uploadFiles(fileList) {
    const files = Array.from(fileList);
    if (uploading || files.length === 0) {
      return;
    }
    uploading = true;
    form.classList.add("is-uploading");
    const maxBytes = Number(form.dataset.maxBytes);
    const results = [];

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      text.textContent = fill(form.dataset.progressText, { done: i + 1, total: files.length });
      if (file.size > maxBytes) {
        results.push({ category: "warning", message: fill(form.dataset.skippedMessage, { name: file.name }) });
        continue;
      }
      results.push(await sendOne(form, file));
    }

    input.value = "";
    const pageFlashes = await refreshFileList();
    showFlashes(pageFlashes.concat(results));
    text.textContent = originalText;
    form.classList.remove("is-uploading");
    uploading = false;
  }

  input.addEventListener("change", function () {
    uploadFiles(input.files);
  });

  // 拖曳經過上傳區時加上提示樣式（用計數避免經過子元素時閃爍）
  let dragDepth = 0;
  zone.addEventListener("dragenter", function (event) {
    event.preventDefault();
    dragDepth++;
    zone.classList.add("is-dragover");
  });
  zone.addEventListener("dragover", function (event) {
    event.preventDefault();
    event.dataTransfer.dropEffect = uploading ? "none" : "copy";
  });
  zone.addEventListener("dragleave", function () {
    dragDepth = Math.max(0, dragDepth - 1);
    if (dragDepth === 0) {
      zone.classList.remove("is-dragover");
    }
  });
  zone.addEventListener("drop", function (event) {
    event.preventDefault();
    dragDepth = 0;
    zone.classList.remove("is-dragover");
    uploadFiles(event.dataTransfer.files);
  });

  // 檔案拖到上傳區以外的地方時，不讓瀏覽器把頁面換成那個檔案
  window.addEventListener("dragover", function (event) {
    event.preventDefault();
  });
  window.addEventListener("drop", function (event) {
    event.preventDefault();
  });

  // 從瀏覽器「上一頁」回來時，把上傳區恢復成可用狀態
  window.addEventListener("pageshow", function (event) {
    if (event.persisted) {
      uploading = false;
      form.classList.remove("is-uploading");
      text.textContent = originalText;
      input.value = "";
    }
  });
}

// 送出一個檔案；後端看到 X-Requested-With 標頭會回 JSON，不會轉址（flash 不會被消耗掉）
async function sendOne(form, file) {
  const data = new FormData();
  data.append("csrf_token", form.querySelector("input[name=csrf_token]").value);
  data.append("the_file", file);
  const failed = { category: "error", message: fill(form.dataset.failedMessage, { name: file.name }) };
  try {
    const response = await fetch(form.action, {
      method: "POST",
      body: data,
      headers: { "X-Requested-With": "fetch" },
      redirect: "manual",
    });
    const type = response.headers.get("Content-Type") || "";
    if (!type.includes("application/json")) {
      return failed;
    }
    const result = await response.json();
    // 成功訊息本身含檔名；警告或錯誤則在前面加上檔名
    if (result.category !== "success") {
      result.message = file.name + "：" + result.message;
    }
    return result;
  } catch (error) {
    return failed;
  }
}

// 重新取得首頁，只替換檔案清單（不重新載入整頁，上傳結果訊息才不會消失）
async function refreshFileList() {
  const list = document.querySelector(".js-file-list");
  try {
    const response = await fetch(window.location.pathname, { headers: { "X-Requested-With": "fetch" } });
    const page = new DOMParser().parseFromString(await response.text(), "text/html");
    const newList = page.querySelector(".js-file-list");
    if (response.ok && newList) {
      list.replaceChildren(...Array.from(newList.childNodes).map(function (node) {
        return document.importNode(node, true);
      }));
    }
    // 這次取得的頁面若剛好帶有其他 flash 訊息，也一併保留
    return Array.from(page.querySelectorAll(".js-flash-list .flash")).map(function (item) {
      return { category: item.className.replace("flash flash-", ""), message: item.textContent };
    });
  } catch (error) {
    // 清單更新失敗時保留原清單，上傳結果訊息仍會顯示
    return [];
  }
}

// ---------- 彈窗：開啟與關閉 ----------
function setupDialogs() {
  document.querySelectorAll(".js-open-dialog").forEach(function (button) {
    button.addEventListener("click", function () {
      const dialog = document.querySelector("." + button.dataset.dialog);
      if (dialog) {
        dialog.showModal();
      }
    });
  });

  document.querySelectorAll(".dialog").forEach(function (dialog) {
    // 點彈窗外的灰色背景也可以關閉（Esc 由瀏覽器內建處理）
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
}

// ---------- 複製分享連結 ----------
// 順序：navigator.clipboard → 選取文字後 execCommand("copy") → 選取文字並提示手動複製
function setupCopy() {
  const copyButton = document.querySelector(".js-copy");
  if (!copyButton) {
    return;
  }
  const linkInput = document.querySelector(".js-share-link");
  const status = document.querySelector(".js-copy-status");
  let timer = null;

  function report(message, manual) {
    clearTimeout(timer);
    status.textContent = message;
    status.classList.toggle("is-manual", manual);
    if (!manual) {
      timer = setTimeout(function () {
        status.textContent = "";
      }, 2500);
    }
  }

  copyButton.addEventListener("click", function () {
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(linkInput.value).then(function () {
        report(copyButton.dataset.copiedText, false);
      }, fallback);
    } else {
      fallback();
    }
  });

  function fallback() {
    const copied = selectAndCopy(linkInput);
    if (copied) {
      report(copyButton.dataset.copiedText, false);
    } else {
      report(copyButton.dataset.manualText, true);
    }
  }
}

// 選取輸入框全部文字並嘗試 execCommand("copy")，回傳是否成功
function selectAndCopy(input) {
  input.focus();
  input.select();
  // iOS 上 select() 對 readonly 輸入框常常無效，需要 setSelectionRange
  input.setSelectionRange(0, input.value.length);
  try {
    return document.execCommand("copy");
  } catch (error) {
    return false;
  }
}

// ---------- 共用 ----------
// 把 "{name}" 這類佔位字換成實際值
function fill(template, values) {
  return template.replace(/\{(\w+)\}/g, function (match, key) {
    return key in values ? String(values[key]) : match;
  });
}

// 在訊息區顯示多則訊息（取代舊的訊息）
function showFlashes(results) {
  const list = document.querySelector(".js-flash-list");
  if (!list) {
    return;
  }
  list.replaceChildren(...results.map(function (result) {
    const item = document.createElement("div");
    item.className = "flash flash-" + result.category;
    item.textContent = result.message;
    return item;
  }));
}
