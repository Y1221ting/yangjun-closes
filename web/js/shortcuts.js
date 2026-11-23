/* 全局快捷键：1 秒内连按两次 F 返回上一页。 */
(function (App) {
  'use strict';

  const DOUBLE_PRESS_MS = 1000;
  const HINT_KEY = 'wardrobe:back-hint';
  let lastPress = 0;

  function isTyping(target) {
    if (!target) return false;
    const tag = target.tagName;
    return (
      tag === 'INPUT' ||
      tag === 'TEXTAREA' ||
      tag === 'SELECT' ||
      target.isContentEditable
    );
  }

  function drawerOpen() {
    const drawer = document.getElementById('drawer');
    return drawer && !drawer.hidden;
  }

  function modalOpen() {
    return Boolean(document.querySelector('.modal'));
  }

  function goBack() {
    if (window.history.length > 1) {
      window.history.back();
    } else if (App.nav) {
      App.nav.toWardrobe();
    }
  }

  function onKeyDown(event) {
    if (event.key.toLowerCase() !== 'f') return;
    if (event.repeat || event.ctrlKey || event.altKey || event.metaKey || event.shiftKey) {
      return;
    }
    if (isTyping(event.target) || modalOpen()) return;

    // 抽屉打开时，先关闭抽屉，不触发返回
    if (drawerOpen()) {
      App.garmentForm.close();
      lastPress = 0;
      return;
    }

    const now = performance.now();
    if (now - lastPress <= DOUBLE_PRESS_MS) {
      lastPress = 0;
      goBack();
    } else {
      lastPress = now;
    }
  }

  function showHintOnce() {
    try {
      if (localStorage.getItem(HINT_KEY)) return;
      localStorage.setItem(HINT_KEY, '1');
      setTimeout(() => {
        App.ui.toast('提示：1 秒内连按两次 F 可返回上一页');
      }, 1600);
    } catch (ignore) {
      /* 隐私模式下 localStorage 可能不可用 */
    }
  }

  function init() {
    document.addEventListener('keydown', onKeyDown);
    showHintOnce();
  }

  App.shortcuts = { init };
})(window.App = window.App || {});
