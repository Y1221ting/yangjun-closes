/* 启动等待封面：等插画、数据、最短展示时长都就绪后淡出。
 * 点击任意处是真的立即跳过，不再等满最短时长。
 * 开关同时写 cookie 和 localStorage：cookie 不区分端口，
 * 程序每次随机端口启动也能记住「关闭欢迎页」。
 */
(function (App) {
  'use strict';

  const KEY = 'yelena-welcome';
  const MIN_SHOW = 1400;
  const MAX_WAIT = 7000;
  const FADE = 720;

  const splash = document.getElementById('splash');
  const art = document.getElementById('splash-art');
  const start = performance.now();

  let imgReady = false;
  let dataReady = false;
  let minDone = false;
  let finished = false;
  let maxTimer = null;
  let minTimer = null;

  function readCookieOff() {
    return document.cookie.split('; ').some((part) => part === `${KEY}=off`);
  }

  function writeCookieOff(off) {
    if (off) {
      document.cookie = `${KEY}=off; max-age=31536000; path=/; SameSite=Lax`;
    } else {
      document.cookie = `${KEY}=; max-age=0; path=/; SameSite=Lax`;
    }
  }

  function isEnabled() {
    try {
      if (readCookieOff()) return false;
      return localStorage.getItem(KEY) !== 'off';
    } catch (err) {
      return !readCookieOff();
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
      /* 忽略存储失败，cookie 仍然生效 */
    }
    writeCookieOff(!on);
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
    if (maxTimer) clearTimeout(maxTimer);
    if (minTimer) clearTimeout(minTimer);
    removeSkipListeners();
    if (!splash) return;

    splash.classList.add('is-leaving');
    window.setTimeout(() => {
      splash.hidden = true;
    }, FADE);
  }

  function maybeFinish() {
    if (imgReady && dataReady && minDone) finish();
  }

  function markImageReady() {
    if (imgReady) return;
    imgReady = true;
    if (splash) splash.classList.add('is-ready');
    maybeFinish();
  }

  function skip() {
    finish();
  }

  function init() {
    if (!splash) return;

    if (!isEnabled()) {
      finished = true;
      splash.hidden = true;
      return;
    }

    if (art) {
      if (art.complete && art.naturalWidth > 0) {
        markImageReady();
      } else {
        art.addEventListener('load', markImageReady, { once: true });
        art.addEventListener('error', markImageReady, { once: true });
        // 图片万一卡住，最多 900ms 也让 LQIP 退出
        window.setTimeout(markImageReady, 900);
      }
    } else {
      markImageReady();
    }

    minTimer = window.setTimeout(() => {
      minDone = true;
      maybeFinish();
    }, Math.max(0, MIN_SHOW - (performance.now() - start)));

    // 数据接口一直不回来时，最多等 7 秒也淡出
    maxTimer = window.setTimeout(finish, MAX_WAIT);

    document.addEventListener('click', skip, true);
    document.addEventListener('keydown', skip, true);
    document.addEventListener('pointerdown', skip, true);
  }

  function hide() {
    dataReady = true;
    maybeFinish();
  }

  App.welcome = { init, hide, isEnabled, setEnabled };
})(window.App = window.App || {});
