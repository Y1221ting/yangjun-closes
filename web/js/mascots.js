/* 七只小人的小彩蛋：点一下跳一跳，弹一句俏皮话。
 * 相机宝宝额外负责打开「添加衣服」；其他小人只说话，不抢主按钮的活。
 */
(function (App) {
  'use strict';

  const LINES = {
    camera: ['叮！相机就位，来拍新衣服～'],
    bench: [
      '坐这儿歇会儿，衣柜我帮你看着～',
      '今天想穿哪件呀？',
      '别急，慢慢挑～',
    ],
    elf: [
      '喵～黑猫说这柜子今天也很整齐',
      '柜子归我管，放心放～',
      '顶柜里还藏着零食（不是）',
    ],
    cow: [
      '这格空得能打滚啦～',
      '放双鞋进来陪我吧！',
      '哞～这格还空着哦',
    ],
    hat: [
      '帽子格空着，我先飞一圈～',
      '挑顶帽子给我戴？',
      '这格还能再住一顶帽子～',
    ],
    bag: [
      '包格空着，装点甜的？',
      '这格还能塞下一个包～',
      '包包装好，出门咯～',
    ],
    drawer: [
      '小抽屉空着，戒指耳钉都可以住～',
      '这格留给小宝贝～',
      '叮，小配饰请入碗～',
    ],
    bowl: [
      '衣柜空空的，先喂它一件衣服吧～',
      '星星棒一挥，新衣服就来啦',
      '慢慢来，第一件总是最特别的',
    ],
    fly: [
      '没找到～换个关键词试试？',
      '我飞了一圈，什么也没看见',
      '要不要清掉筛选再看看？',
    ],
    spoon: [
      '给衣柜换个口味？现在这锅是蓝水彩味的～',
      '搅一搅，今天的衣柜更香了',
      '外观这锅汤，还能再调调味',
    ],
    outfit: [
      '还没有搭配，来搭第一套吧～',
      '把喜欢的衣服拖到一起，就是一套～',
      '衣橱都准备好了，就等你～',
    ],
    'outfit-filter': [
      '这套搭配躲起来了～换个词找找？',
      '没有找到，要不要清掉筛选？',
      '我飞了一圈，没看见这套～',
    ],
    recycle: [
      '回收站很干净，今天也没有走丢的衣服～',
      '这里空空的，大家都还在衣柜里～',
      '没有要找回的东西，真好～',
    ],
  };

  const ACTIONS = {
    camera() {
      const add = document.getElementById('btn-add');
      if (add && !add.disabled) add.click();
    },
  };

  const lastPlayed = new Map();
  let bubble = null;
  let hideTimer = null;

  function ensureBubble() {
    if (bubble) return bubble;
    bubble = document.createElement('div');
    bubble.className = 'mascot-bubble';
    bubble.setAttribute('role', 'status');
    bubble.setAttribute('aria-live', 'polite');
    document.body.appendChild(bubble);
    return bubble;
  }

  function hideBubble() {
    if (hideTimer) clearTimeout(hideTimer);
    hideTimer = null;
    if (bubble) bubble.classList.remove('is-visible');
  }

  function showBubble(button, key) {
    const lines = LINES[key] || [];
    if (!lines.length) return;

    const el = ensureBubble();
    el.textContent = lines[Math.floor(Math.random() * lines.length)];
    el.classList.remove('is-visible', 'mascot-bubble--below');
    el.style.left = '0px';
    el.style.top = '0px';
    void el.offsetWidth;

    const rect = button.getBoundingClientRect();
    const width = el.offsetWidth;
    const height = el.offsetHeight;
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const margin = 12;

    const center = rect.left + rect.width / 2;
    const left = Math.min(
      Math.max(center, width / 2 + margin),
      Math.max(width / 2 + margin, vw - width / 2 - margin)
    );

    let top = rect.top - height - 10;
    let below = false;
    if (top < margin) {
      top = rect.bottom + 10;
      below = true;
    }
    top = Math.min(Math.max(top, margin), Math.max(margin, vh - height - margin));

    el.style.left = `${left}px`;
    el.style.top = `${top}px`;
    el.classList.toggle('mascot-bubble--below', below);
    requestAnimationFrame(() => el.classList.add('is-visible'));

    if (hideTimer) clearTimeout(hideTimer);
    hideTimer = window.setTimeout(() => {
      el.classList.remove('is-visible');
      hideTimer = null;
    }, 2600);
  }

  function play(button) {
    const key = button.dataset.mascot;
    if (!key) return;

    // 同一个角色在不同位置可以有不同台词，例如帽子格的飞行宝宝
    const lineKey = button.dataset.lines || key;
    const now = Date.now();
    const last = lastPlayed.get(lineKey) || 0;
    if (now - last < 260) return;
    lastPlayed.set(lineKey, now);

    button.classList.remove('is-playing');
    void button.offsetWidth;
    button.classList.add('is-playing');
    window.setTimeout(() => button.classList.remove('is-playing'), 620);

    showBubble(button, lineKey);

    const action = ACTIONS[key];
    if (action) {
      window.setTimeout(() => {
        hideBubble();
        action();
      }, 420);
    }
  }

  function onClick(event) {
    const button = event.target.closest('[data-mascot]');
    if (!button) return;
    event.preventDefault();
    event.stopPropagation();
    play(button);
  }

  function init() {
    document.addEventListener('click', onClick, true);
  }

  App.mascots = { init };
})(window.App = window.App || {});
