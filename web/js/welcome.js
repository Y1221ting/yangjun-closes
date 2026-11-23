/* 启动欢迎页：等程序启动完成后淡出，点击任意处可跳过。 */
(function (App) {
  'use strict';

  const KEY = 'yt-welcome';
  const MIN_SHOW = 1600;
  const MAX_WAIT = 7000;
  const FADE = 520;

  const el = document.getElementById('welcome');
  const start = performance.now();
  let finished = false;
  let timer = null;

  function isEnabled() {
    try {
      return localStorage.getItem(KEY) !== 'off';
    } catch (err) {
      return true;
    }
  }

  function setEnabled(on) {
    try {
      if (on) {
        localStorage.removeItem(KEY);
      } else {
        localStorage.setItem(KEY, 'off');
      }
    } catch (err) {
      /* 忽略存储失败 */
    }
    document.documentElement.classList.toggle('no-welcome', !on);
  }

  function removeSkipListeners() {
    document.removeEventListener('click', skip, true);
    document.removeEventListener('keydown', skip, true);
    document.removeEventListener('pointerdown', skip, true);
  }

  function finish() {
    if (finished) return;
    finished = true;
    if (timer) clearTimeout(timer);
    removeSkipListeners();
    if (el.hidden) return;

    const wait = Math.max(0, MIN_SHOW - (performance.now() - start));
    window.setTimeout(() => {
      el.classList.add('is-leaving');
      window.setTimeout(() => {
        el.hidden = true;
      }, FADE);
    }, wait);
  }

  function skip() {
    finish();
  }

  function init() {
    if (!isEnabled()) {
      el.hidden = true;
      return;
    }
    document.addEventListener('click', skip, true);
    document.addEventListener('keydown', skip, true);
    document.addEventListener('pointerdown', skip, true);
    // 启动接口万一一直没回来，最多等 7 秒也淡出
    timer = window.setTimeout(finish, MAX_WAIT);
  }

  App.welcome = { init, hide: finish, isEnabled, setEnabled };
})(window.App = window.App || {});
