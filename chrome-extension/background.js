class BackgroundService {
  constructor() {
    this.isRecording = false;
    this.hostFilter = '';
    this.recordedRequests = [];
    this.recordCount = 0;
    this._boundBeforeSendHeaders = null;
    this._boundResponseStarted = null;
    this.initialize();
  }

  async initialize() {
    await this.loadConfig();
    await this.loadRecordingState();
    this.setupEventListeners();
  }

  async loadConfig() {
    const config = await chrome.storage.local.get(['hostFilter']);
    if (config.hostFilter) {
      this.hostFilter = config.hostFilter;
    }
  }

  async loadRecordingState() {
    const state = await chrome.storage.local.get(['isRecording', 'recordedRequests', 'recordCount']);
    if (state.isRecording) {
      this.isRecording = true;
      this.recordedRequests = state.recordedRequests || [];
      this.recordCount = state.recordCount || 0;
      this.setupRequestListeners();
    }
  }

  async saveRecordingState() {
    await chrome.storage.local.set({
      isRecording: this.isRecording,
      recordedRequests: this.recordedRequests,
      recordCount: this.recordCount
    });
  }

  setupEventListeners() {
    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
      switch (message.action) {
        case 'startRecording':
          this.startRecording();
          sendResponse({ success: true });
          break;
        case 'stopRecording':
          this.stopRecording();
          // 尝试打开插件面板
          if (sender.tab) {
            try {
              chrome.action.openPopup({ tabId: sender.tab.id });
            } catch (error) {
              console.warn('无法打开插件面板:', error);
            }
          }
          sendResponse({ success: true, data: this.recordedRequests });
          break;
        case 'getRecordingStatus':
          sendResponse({ success: true, isRecording: this.isRecording, recordCount: this.recordCount });
          break;
        case 'getRecordCount':
          sendResponse({ success: true, recordCount: this.recordCount });
          break;
        case 'setHostFilter':
          this.hostFilter = message.host;
          chrome.storage.local.set({ hostFilter: message.host });
          sendResponse({ success: true });
          break;
        case 'exportData':
          sendResponse({ success: true, data: this.recordedRequests });
          break;
        case 'syncToBackend':
          this.syncToBackend().then(result => {
            sendResponse({ success: result.success, message: result.message });
          });
          return true;
        default:
          sendResponse({ success: false, message: 'Unknown action' });
      }
    });
  }

  startRecording() {
    this.isRecording = true;
    this.recordedRequests = [];
    this.recordCount = 0;
    this.setupRequestListeners();
    this.saveRecordingState();
  }

  stopRecording() {
    this.isRecording = false;
    this.removeRequestListeners();
    this.saveRecordingState();
  }

  setupRequestListeners() {
    if (this._boundBeforeSendHeaders) {
      chrome.webRequest.onBeforeSendHeaders.removeListener(this._boundBeforeSendHeaders);
    }
    if (this._boundResponseStarted) {
      chrome.webRequest.onResponseStarted.removeListener(this._boundResponseStarted);
    }

    this._boundBeforeSendHeaders = this.handleBeforeSendHeaders.bind(this);
    this._boundResponseStarted = this.handleResponseStarted.bind(this);

    chrome.webRequest.onBeforeSendHeaders.addListener(
      this._boundBeforeSendHeaders,
      { urls: ['<all_urls>'] },
      ['requestHeaders']
    );

    chrome.webRequest.onResponseStarted.addListener(
      this._boundResponseStarted,
      { urls: ['<all_urls>'] },
      ['responseHeaders']
    );
  }

  removeRequestListeners() {
    if (this._boundBeforeSendHeaders) {
      chrome.webRequest.onBeforeSendHeaders.removeListener(this._boundBeforeSendHeaders);
      this._boundBeforeSendHeaders = null;
    }
    if (this._boundResponseStarted) {
      chrome.webRequest.onResponseStarted.removeListener(this._boundResponseStarted);
      this._boundResponseStarted = null;
    }
  }

  handleBeforeSendHeaders(details) {
    if (!this.isRecording) return;

    // 只抓取fetch和XHR请求
    // 通过检查initiatorType或其他特征来判断
    // 注意：webRequest API可能无法直接获取initiatorType，需要通过其他方式判断
    
    // 过滤掉非fetch/XHR请求
    // 1. 过滤掉浏览器扩展发起的请求
    if (details.initiator && details.initiator.startsWith('chrome-extension://')) {
      return;
    }
    
    // 2. 过滤掉一些常见的非API请求类型
    const url = new URL(details.url);
    const requestHost = `${url.protocol}//${url.host}`;
    
    if (this.hostFilter && requestHost !== this.hostFilter) return;
    
    // 3. 过滤掉静态资源请求
    const staticExtensions = ['.js', '.css', '.jpg', '.jpeg', '.png', '.gif', '.ico', '.svg', '.woff', '.woff2', '.ttf', '.eot'];
    const pathname = url.pathname.toLowerCase();
    
    for (const ext of staticExtensions) {
      if (pathname.endsWith(ext)) {
        return;
      }
    }
    
    // 4. 过滤掉一些常见的静态资源路径
    const staticPaths = ['/static/', '/assets/', '/images/', '/css/', '/js/', '/fonts/'];
    for (const path of staticPaths) {
      if (pathname.includes(path)) {
        return;
      }
    }

    const requestData = {
      id: details.requestId,
      url: details.url,
      method: details.method,
      requestHeaders: details.requestHeaders,
      timestamp: Date.now()
    };

    this.recordedRequests.push(requestData);
    this.recordCount++;
    this.saveRecordingState();
  }

  handleResponseStarted(details) {
    if (!this.isRecording) return;

    const request = this.recordedRequests.find(r => r.id === details.requestId);
    if (request) {
      request.statusCode = details.statusCode;
      request.responseHeaders = details.responseHeaders;
      this.saveRecordingState();
    }
  }
  

  async syncToBackend() {
    try {
      const backendUrl = 'http://localhost:5000/api/interface/record';
      const response = await fetch(backendUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          requests: this.recordedRequests
        })
      });

      if (response.ok) {
        return { success: true, message: '数据同步成功' };
      } else {
        return { success: false, message: '数据同步失败' };
      }
    } catch (error) {
      return { success: false, message: '网络错误：' + error.message };
    }
  }
}

new BackgroundService();