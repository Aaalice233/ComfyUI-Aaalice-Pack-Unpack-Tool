import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

// 简化版：移除未使用的spinner变量

const style = `
/* 简化版核心样式 */
.cpack-modal {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  background: #1a1a1a;
  padding: 20px;
  border-radius: 8px;
  z-index: 1000;
  color: white;
  min-width: 360px;
}

.cpack-input {
  width: 100%;
  padding: 8px;
  background: #333;
  border: 1px solid #444;
  border-radius: 4px;
  color: white;
  box-sizing: border-box;
}

.cpack-btn {
  padding: 6px 12px;
  background: #666;
  border: none;
  border-radius: 4px;
  color: white;
  cursor: pointer;
}

.cpack-btn.primary {
  background: #00a67d;
}

.cpack-btn.primary:disabled {
  background: #81a39b;
  cursor: not-allowed;
}

.cpack-btn-container {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.cpack-title {
  margin-bottom: 15px;
  font-size: 1.3em;
  font-weight: bold;
}

.cpack-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 999;
}

.cpack-form-item {
  margin-bottom: 15px;
}

.cpack-form-item:last-child {
  margin-bottom: -5px;
}

.cpack-form-item label {
  margin-bottom: 5px;
}

.error-message {
  color: #ff8383;
  margin-top: 5px;
  display: none;
  font-size: 0.9em;
}
`

// 简化版：移除文件选择相关类和函数
// TreeState 和 FileTreeList 类已移除，改为自动处理所有文件

// 简化版：移除ModelList类，不再提供模型选择功能

function createModal(modal) {
  const overlay = document.createElement("div");
  overlay.className = "cpack-overlay";

  document.body.appendChild(overlay);
  document.body.appendChild(modal);

  return {
    close: () => {
      modal.remove();
      overlay.remove();
    }
  };
}



async function createPackModal() {
  return new Promise((resolve) => {
    const modal = document.createElement("div");
    modal.className = "cpack-modal";
    modal.id = "input-modal";

    const title = document.createElement("div");
    title.textContent = "Package Workflow";
    title.className = "cpack-title";

    const form = document.createElement("form");
    form.innerHTML = `
      <div class="cpack-form-item">
        <label for="filename">Name</label>
        <input type="text" class="cpack-input" name="filename" value="${localStorage.getItem('cpack-bento-name') || 'comfy-pack-pkg'}" />
      </div>
      <div class="cpack-form-item">
        <label for="completion_message">Completion Message (optional)</label>
        <textarea class="cpack-input" name="completion_message" rows="3" placeholder="例如：欢迎加入Aaalice的服务器！ https://discord.gg/R48n6GwXzD">${localStorage.getItem('cpack-completion-message') || ''}</textarea>
        <small style="color: #888; font-size: 12px;">解包完成后显示的自定义消息，支持链接</small>
      </div>
      <div id="package-options-container"></div>
    `;

    const buttonContainer = document.createElement("div");
    buttonContainer.className = "cpack-btn-container";

    const confirmButton = document.createElement("button");
    confirmButton.textContent = "Pack";
    confirmButton.className = "cpack-btn primary";
    confirmButton.disabled = true;

    const cancelButton = document.createElement("button");
    cancelButton.textContent = "Cancel";
    cancelButton.className = "cpack-btn";

    buttonContainer.appendChild(cancelButton);
    buttonContainer.appendChild(confirmButton);
    modal.appendChild(title);
    modal.appendChild(form);
    modal.appendChild(buttonContainer);

    const { close } = createModal(modal);

    const packageOptionsContainer = form.querySelector("#package-options-container");
    const packageOptions = new PackageOptions(form, "pack-models-list", "pack-files-list", true);
    packageOptionsContainer.innerHTML = packageOptions.getHtml();

    // 简化版：立即初始化，无需加载文件列表
    packageOptions.init();
    confirmButton.disabled = false;

    confirmButton.onclick = () => {
      const filename = form.querySelector("input[name='filename']").value.trim();
      const completionMessage = form.querySelector("textarea[name='completion_message']").value.trim();
      if (filename) {
        // Save to localStorage
        localStorage.setItem('cpack-bento-name', filename);
        localStorage.setItem('cpack-completion-message', completionMessage);
        const selectedData = packageOptions.getSelectedData();
        close();
        resolve({
          filename,
          completionMessage,
          files: selectedData.files
        });
      }
    };

    cancelButton.onclick = () => {
      close();
      resolve(null);
    };

    const filenameInput = form.querySelector("input[name='filename']");
    filenameInput.addEventListener("keyup", (e) => {
      if (e.key === "Enter") {
        confirmButton.click();
      }
    });

    filenameInput.select();
  });
}

function createDownloadModal() {
  const modal = document.createElement("div");
  modal.className = "cpack-modal";
  modal.id = "download-modal";

  const title = document.createElement("div");
  title.textContent = "Packaging...";
  title.style.marginBottom = "15px";
  title.style.color = "#fff";

  const hint = document.createElement("div");
  hint.textContent = "简化版打包：自动处理所有必需文件，不包含模型哈希数据。";
  hint.style.cssText = "color: #00a67d; font-size: 0.9em; margin-bottom: 15px;";

  const progress = document.createElement("div");
  progress.style.cssText = `
    width: 100%;
    height: 20px;
    background: #333;
    border-radius: 10px;
    overflow: hidden;
  `;

  const progressBar = document.createElement("div");
  progressBar.style.cssText = `
    width: 0%;
    height: 100%;
    background: #00a67d;
    transition: width 0.3s ease;
  `;

  progress.appendChild(progressBar);

  // Log container
  const logContainer = document.createElement("div");
  logContainer.style.cssText = `
    height: 150px;
    overflow-y: auto;
    background: #1a1a1a;
    border: 1px solid #333;
    border-radius: 5px;
    padding: 8px;
    margin-top: 15px;
    font-family: 'Consolas', 'Monaco', monospace;
    font-size: 12px;
    line-height: 1.5;
  `;

  // Time display
  const timeDisplay = document.createElement("div");
  timeDisplay.style.cssText = `
    margin-top: 10px;
    color: #888;
    font-size: 0.9em;
    text-align: center;
  `;
  timeDisplay.textContent = "已用时间: 0s | 预计剩余: --";

  modal.appendChild(title);
  modal.appendChild(hint);
  modal.appendChild(progress);
  modal.appendChild(logContainer);
  modal.appendChild(timeDisplay);

  const { close } = createModal(modal);

  const startTime = Date.now();

  return {
    updateProgress: (percent) => {
      progressBar.style.width = `${percent}%`;
    },
    addLog: (message, level = "info") => {
      const logEntry = document.createElement("div");
      logEntry.style.marginBottom = "3px";

      // Color based on level
      let color = "#aaa"; // default info
      if (level === "success") color = "#4ade80";
      else if (level === "progress") color = "#fbbf24";
      else if (level === "cache") color = "#fb923c";
      else if (level === "info") color = "#60a5fa";

      const timestamp = new Date().toLocaleTimeString();
      logEntry.innerHTML = `<span style="color: #666;">[${timestamp}]</span> <span style="color: ${color};">${message}</span>`;

      logContainer.appendChild(logEntry);
      // Auto scroll to bottom
      logContainer.scrollTop = logContainer.scrollHeight;
    },
    updateTime: (elapsed, eta) => {
      const elapsedStr = elapsed < 60 ? `${elapsed}s` : `${Math.floor(elapsed / 60)}m ${elapsed % 60}s`;
      const etaStr = eta > 0 ? (eta < 60 ? `${Math.floor(eta)}s` : `${Math.floor(eta / 60)}m ${Math.floor(eta % 60)}s`) : "--";
      timeDisplay.textContent = `已用时间: ${elapsedStr} | 预计剩余: ${etaStr}`;
    },
    getStartTime: () => startTime,
    close
  };
}

async function packageAction() {
  if (document.getElementById("input-modal")) return;
  if (document.getElementById("download-modal")) return;
  const result = await createPackModal();
  if (!result) return;

  const downloadModal = createDownloadModal();

  // Setup WebSocket progress listener
  const progressHandler = (event) => {
    const { data } = event.detail;
    if (data && data.type === "pack_progress") {
      const progressData = data.data;

      // Update progress bar
      if (progressData.percentage > 0) {
        downloadModal.updateProgress(progressData.percentage);
      }

      // Add log entry
      downloadModal.addLog(progressData.message, progressData.level);

      // Update time display
      const startTime = downloadModal.getStartTime();
      const elapsed = Math.floor((Date.now() - startTime) / 1000);
      const eta = progressData.eta || 0;
      downloadModal.updateTime(elapsed, eta);
    }
  };

  api.addEventListener("pack_progress", progressHandler);

  // Timer for elapsed time update
  const timeUpdateInterval = setInterval(() => {
    const startTime = downloadModal.getStartTime();
    const elapsed = Math.floor((Date.now() - startTime) / 1000);
    downloadModal.updateTime(elapsed, 0);
  }, 1000);

  try {
    downloadModal.addLog("开始准备工作流数据...", "info");
    const { workflow, output: workflow_api } = await app.graphToPrompt();

    downloadModal.addLog("工作流序列化完成", "info");
    const body = JSON.stringify({
      workflow,
      workflow_api,
      files: [],  // 简化版：空文件列表，后端将自动处理所有文件
      filename: result.filename,  // Include filename for custom naming
      completion_message: result.completionMessage,  // Include completion message
      client_id: api.clientId  // Include client_id for WebSocket routing
    });

    downloadModal.addLog("正在发送打包请求...", "info");
    const resp = await api.fetchApi("/bentoml/pack", {
      method: "POST",
      body,
      headers: { "Content-Type": "application/json" }
    });

    const downloadUrl = (await resp.json())["download_url"];

    downloadModal.addLog("打包完成！开始下载...", "success");
    const link = document.createElement("a");
    link.href = downloadUrl;
    link.download = result.filename + ".cpack.zip";
    link.click();

    setTimeout(() => {
      clearInterval(timeUpdateInterval);
      api.removeEventListener("pack_progress", progressHandler);
      downloadModal.close();
    }, 2000);
  } catch (error) {
    console.error("Package failed:", error);
    downloadModal.addLog(`打包失败: ${error.message}`, "error");
    clearInterval(timeUpdateInterval);
    api.removeEventListener("pack_progress", progressHandler);
    setTimeout(() => {
      downloadModal.close();
    }, 3000);
  }
}

// 简化版：移除Serve和Deploy功能

class PackageOptions {
  constructor(container, modelsListId, filesListId, defaultOpen = true) {
    this.container = container;
    this.modelsListId = modelsListId;
    this.filesListId = filesListId;
    this.modelListComponent = null;
    this.fileListComponent = null;
    this.defaultOpen = defaultOpen;
  }

  getHtml() {
    return `
      <div class="cpack-form-item">
        <div style="padding: 10px; background: rgba(76, 175, 80, 0.1); border: 1px solid rgba(76, 175, 80, 0.3); border-radius: 4px; margin-bottom: 15px;">
          <h5 style="margin: 0 0 10px 0; color: #ffc107;">📋 简化版本说明</h5>
          <p style="margin: 5px 0; color: #ccc; font-size: 0.9em;">
            • 自动包含所有必需文件<br>
            • 不会包含模型哈希数据<br>
            • 工作流用到的模型文件需自行下载<br>
            • 一键打包完整工作流
          </p>
        </div>
      </div>
    `;
  }

  async init() {
    // 简化版：无需初始化文件列表
    console.log("简化版打包模式：自动处理所有必需文件");
  }

  getSelectedData() {
    // 简化版：返回空文件列表，后端将自动处理
    return {
      files: []
    };
  }
}

// 简化版：移除Deploy相关表单和函数

// 简化版：移除Serve状态相关函数


// 简化版：移除Building模态框相关函数

app.registerExtension({
  name: "Comfy.CPackExtension",

  async setup() {
    const styleTag = document.createElement("style");
    styleTag.innerHTML = style;
    document.head.appendChild(styleTag);
    const menu = document.querySelector(".comfy-menu");
    const separator = document.createElement("hr");

    separator.style.margin = "20px 0";
    separator.style.width = "100%";
    menu.append(separator);

    const packButton = document.createElement("button");
    packButton.textContent = "Package";
    packButton.onclick = packageAction;
    menu.append(packButton);

    // 简化版：移除Serve和Deploy按钮


    try {
      // new style Manager buttons

      // Package button into new style Manager button
      let cmGroup1 = new (await import("../../scripts/ui/components/buttonGroup.js")).ComfyButtonGroup(
        new (await import("../../scripts/ui/components/button.js")).ComfyButton({
          icon: "package-variant-closed",
          action: packageAction,
          tooltip: "Comfy-Pack",
          content: "Package",
          classList: "comfyui-button comfyui-menu-mobile-collapse primary"
        }).element,
      );

      app.menu?.settingsGroup.element.before(cmGroup1.element);

      // 简化版：移除Serve和Deploy按钮组
    }
    catch (exception) {
      console.log('ComfyUI is outdated. New style menu based features are disabled.');
    }
  }
});
