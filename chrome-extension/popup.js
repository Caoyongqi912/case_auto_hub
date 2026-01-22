class PopupManager {
  constructor() {
    this.initializeElements();
    this.setupEventListeners();
    this.loadSavedHost();
  }

  initializeElements() {
    this.hostInput = document.getElementById('hostInput');
    this.saveHostBtn = document.getElementById('saveHostBtn');
    this.startRecordBtn = document.getElementById('startRecordBtn');
    this.stopRecordBtn = document.getElementById('stopRecordBtn');
    this.exportBtn = document.getElementById('exportBtn');
    this.exportFormat = document.getElementById('exportFormat');
    this.syncBtn = document.getElementById('syncBtn');
    this.statusText = document.getElementById('statusText');
  }

  setupEventListeners() {
    this.saveHostBtn.addEventListener('click', () => this.saveHost());
    this.startRecordBtn.addEventListener('click', () => this.startRecording());
    this.stopRecordBtn.addEventListener('click', () => this.stopRecording());
    this.exportBtn.addEventListener('click', () => this.exportData());
    this.syncBtn.addEventListener('click', () => this.syncToBackend());
  }

  async loadSavedHost() {
    const result = await chrome.storage.local.get(['hostFilter']);
    if (result.hostFilter) {
      this.hostInput.value = result.hostFilter;
    }
  }

  async saveHost() {
    const host = this.hostInput.value.trim();
    if (!host) {
      this.showStatus('请输入有效的Host地址', 'error');
      return;
    }

    try {
      new URL(host);
    } catch (error) {
      this.showStatus('Host地址格式不正确', 'error');
      return;
    }

    await chrome.runtime.sendMessage({ action: 'setHostFilter', host });
    this.showStatus('Host配置保存成功', 'success');
  }

  async startRecording() {
    await chrome.runtime.sendMessage({ action: 'startRecording' });
    this.toggleRecordingState(true);
    this.showStatus('开始录制', 'success');
    
    // 通知content script显示悬浮窗
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      function: () => {
        window.postMessage({ action: 'showFloatingWindow' }, '*');
      }
    });

    // 关闭popup
    window.close();
  }

  async stopRecording() {
    const result = await chrome.runtime.sendMessage({ action: 'stopRecording' });
    this.toggleRecordingState(false);
    this.showStatus('结束录制', 'success');
  }

  async exportData() {
    try {
      const result = await chrome.runtime.sendMessage({ action: 'exportData' });
      if (result.success) {
        const format = this.exportFormat.value;
        if (format === 'json') {
          this.downloadAsJSON(result.data);
        } else if (format === 'har') {
          this.downloadAsHAR(result.data);
        }
        this.showStatus('数据导出成功', 'success');
      } else {
        this.showStatus('数据导出失败', 'error');
      }
    } catch (error) {
      this.showStatus('导出过程出错: ' + error.message, 'error');
    }
  }

  async syncToBackend() {
    try {
      this.showStatus('正在同步数据...', 'success');
      const result = await chrome.runtime.sendMessage({ action: 'syncToBackend' });
      this.showStatus(result.message, result.success ? 'success' : 'error');
    } catch (error) {
      this.showStatus('同步过程出错: ' + error.message, 'error');
    }
  }

  toggleRecordingState(isRecording) {
    this.startRecordBtn.disabled = isRecording;
    this.stopRecordBtn.disabled = !isRecording;
  }

  showStatus(message, type) {
    this.statusText.textContent = `状态：${message}`;
    this.statusText.style.color = type === 'error' ? '#f44336' : '#4CAF50';
  }

  downloadData(data) {
    this.downloadAsJSON(data);
  }

  downloadAsJSON(data) {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `api-records-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  downloadAsHAR(data) {
    const har = {
      log: {
        version: '1.2',
        creator: {
          name: 'API录制助手',
          version: '1.0'
        },
        entries: data.map(request => ({
          startedDateTime: new Date(request.timestamp).toISOString(),
          time: 0,
          request: {
            method: request.method,
            url: request.url,
            headers: request.requestHeaders || [],
            queryString: [],
            cookies: [],
            headersSize: -1,
            bodySize: -1
          },
          response: {
            status: request.statusCode || 0,
            statusText: '',
            headers: request.responseHeaders || [],
            cookies: [],
            content: {
              size: -1,
              mimeType: 'application/json'
            },
            redirectURL: '',
            headersSize: -1,
            bodySize: -1
          },
          cache: {},
          timings: {
            blocked: -1,
            dns: -1,
            connect: -1,
            send: 0,
            wait: 0,
            receive: 0,
            ssl: -1
          }
        }))
      }
    };

    const blob = new Blob([JSON.stringify(har, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `api-records-${Date.now()}.har`;
    a.click();
    URL.revokeObjectURL(url);
  }
}

new PopupManager();