class ContentManager {
  constructor() {
    this.floatingWindow = null;
    this.isRecording = false;
    this.countUpdateTimer = null;
    this.setupEventListeners();
    // 立即检查状态
    this.checkRecordingStatus();
    // 延迟再次检查，确保状态完全恢复
    setTimeout(() => this.checkRecordingStatus(), 500);
    // 再次延迟检查，确保万无一失
    setTimeout(() => this.checkRecordingStatus(), 1000);
  }

  setupEventListeners() {
    // 监听来自popup的消息
    window.addEventListener('message', (event) => {
      if (event.data.action === 'showFloatingWindow') {
        this.checkRecordingStatus();
      }
    });

    // 监听浏览器前进/后退事件
    window.addEventListener('popstate', () => {
      this.checkRecordingStatus();
    });

    // 监听URL hash变化事件
    window.addEventListener('hashchange', () => {
      this.checkRecordingStatus();
    });

    // 监听DOM变化，确保悬浮窗在DOM更新后仍然存在
    const observer = new MutationObserver(() => {
      if (this.isRecording && !this.floatingWindow) {
        this.showFloatingWindow(this._lastRecordCount || 0);
        this.checkRecordingStatus();
      }
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true
    });

    // 监听页面可见性变化（Tab切换时）
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') {
        this.checkRecordingStatus();
      }
    });

    // 监听页面加载完成事件
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', () => {
        this.checkRecordingStatus();
      });
    } else {
      this.checkRecordingStatus();
    }

    // 监听页面完全加载事件
    window.addEventListener('load', () => {
      this.checkRecordingStatus();
    });

    // 定期检查录制状态（每3秒），防止状态不同步
    setInterval(() => {
      this.checkRecordingStatus();
    }, 3000);
  }

  async checkRecordingStatus() {
    let retries = 5;
    let delay = 200;

    while (retries > 0) {
      try {
        console.log('检查录制状态...');
        const result = await chrome.runtime.sendMessage({ action: 'getRecordingStatus' });
        console.log('获取录制状态结果:', result);
        
        if (result && result.success) {
          if (result.isRecording) {
            console.log('恢复录制状态，计数:', result.recordCount);
            this.showFloatingWindow(result.recordCount || 0);
            // 开始定时更新计数
            this.startCountUpdate();
            this.isRecording = true;
          } else {
            console.log('当前未在录制');
            this.hideFloatingWindow();
            this.isRecording = false;
          }
          return;
        } else {
          console.warn('获取录制状态失败，结果:', result);
        }
      } catch (error) {
        console.warn('检查录制状态失败，重试中:', error.message);
      }
      
      retries--;
      if (retries > 0) {
        await new Promise(resolve => setTimeout(resolve, delay));
        delay *= 1.5;
      } else {
        console.error('检查录制状态最终失败');
      }
    }
  }

  startCountUpdate() {
    // 清除之前的定时器
    if (this.countUpdateTimer) {
      clearInterval(this.countUpdateTimer);
    }

    // 每2秒更新一次计数
    this.countUpdateTimer = setInterval(async () => {
      try {
        const result = await chrome.runtime.sendMessage({ action: 'getRecordCount' });
        if (result.success && this.floatingWindow) {
          this.updateFloatingWindowCount(result.recordCount || 0);
        }
      } catch (error) {
        console.error('更新计数失败:', error);
      }
    }, 2000);
  }

  stopCountUpdate() {
    if (this.countUpdateTimer) {
      clearInterval(this.countUpdateTimer);
      this.countUpdateTimer = null;
    }
  }

  updateFloatingWindowCount(count) {
    if (this.floatingWindow) {
      const countElement = this.floatingWindow.querySelector('.record-count');
      if (countElement) {
        countElement.textContent = `已录制: ${count} 个接口`;
      }
    }
  }

  showFloatingWindow(count = 0) {
    if (this.floatingWindow) {
      this.floatingWindow.remove();
    }

    this._lastRecordCount = count;

    this.floatingWindow = document.createElement('div');
    this.floatingWindow.style.cssText = `
      position: fixed;
      right: 10px;
      top: 50%;
      transform: translateY(-50%);
      background-color: #4CAF50;
      color: white;
      padding: 15px;
      border-radius: 8px;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
      z-index: 999999;
      cursor: pointer;
      text-align: center;
      min-width: 100px;
      animation: pulse 2s infinite;
    `;
    this.floatingWindow.innerHTML = `
      <div>录制中</div>
      <div class="record-count" style="font-size: 12px; margin: 5px 0;">已录制: ${count} 个接口</div>
      <div style="font-size: 12px;">点击结束</div>
    `;

    // 添加动画样式
    const style = document.createElement('style');
    style.textContent = `
      @keyframes pulse {
        0% {
          box-shadow: 0 0 0 0 rgba(76, 175, 80, 0.7);
        }
        70% {
          box-shadow: 0 0 0 10px rgba(76, 175, 80, 0);
        }
        100% {
          box-shadow: 0 0 0 0 rgba(76, 175, 80, 0);
        }
      }
    `;
    document.head.appendChild(style);

    this.floatingWindow.addEventListener('click', () => {
      this.stopRecording();
    });

    document.body.appendChild(this.floatingWindow);
    this.isRecording = true;
  }

  async stopRecording() {
    try {
      await chrome.runtime.sendMessage({ action: 'stopRecording' });
      this.hideFloatingWindow();
      this.showStopRecordingNotification();
    } catch (error) {
      console.error('停止录制失败:', error);
    }
  }

  showStopRecordingNotification() {
    // 创建停止录制通知
    const notification = document.createElement('div');
    notification.style.cssText = `
      position: fixed;
      right: 10px;
      top: 20px;
      background-color: #4CAF50;
      color: white;
      padding: 12px 16px;
      border-radius: 4px;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
      z-index: 999999;
      font-size: 14px;
      animation: slideIn 0.3s ease-out;
    `;

    // 添加动画样式
    const style = document.createElement('style');
    style.textContent = `
      @keyframes slideIn {
        from {
          transform: translateX(100%);
          opacity: 0;
        }
        to {
          transform: translateX(0);
          opacity: 1;
        }
      }
    `;
    document.head.appendChild(style);

    notification.innerHTML = `
      <div>录制已结束</div>
      <div style="font-size: 12px; margin-top: 4px;">点击插件图标打开面板进行导出或同步</div>
    `;

    document.body.appendChild(notification);

    // 3秒后自动隐藏通知
    setTimeout(() => {
      notification.style.animation = 'slideIn 0.3s ease-out reverse';
      setTimeout(() => {
        notification.remove();
        style.remove();
      }, 300);
    }, 3000);
  }

  hideFloatingWindow() {
    if (this.floatingWindow) {
      this.floatingWindow.remove();
      this.floatingWindow = null;
    }
    this.stopCountUpdate();
    this.isRecording = false;
  }
}

new ContentManager();