/* 七只小人的小彩蛋：点一下跳一跳，弹一句俏皮话。
 * 相机宝宝额外负责打开「添加衣服」；其他小人只说话，不抢主按钮的活。
 */
(function (App) {
  'use strict';

  // 性格：相机=元气，长椅=慢悠悠，精灵=猫系傲娇，奶牛=憨憨，
  // 碗里=温柔，飞行=好奇，勺子=贪吃。
  const LINES = {
    camera: [
      '咔嚓！今天也要拍得漂漂亮亮～',
      '相机就位，新衣服快过来！',
      '灯光、角度、微笑，全都准备好了！',
    ],
    bench: [
      '坐这儿歇会儿，衣柜不着急～',
      '慢慢挑，今天有的是时间～',
      '先坐一会儿，想好再穿～',
    ],
    elf: [
      '喵……这柜子还算整齐吧',
      '黑猫说它勉强满意，哼',
      '别乱放哦，我会盯着你的',
    ],
    cow: [
      '哞！这格空得能翻跟头～',
      '鞋子鞋子快进来，我数到三！',
      '这格好大，我先打个滚～',
    ],
    hat: [
      '帽子格空着，我先试飞一圈～',
      '这顶帽子适合我吗？',
      '帽檐底下好像很适合打盹～',
    ],
    bag: [
      '包格空着，能装下一整袋小饼干吗？',
      '这个包看起来很适合装零食～',
      '包包装满，出门吃好吃的！',
    ],
    drawer: [
      '小抽屉空着，小戒指小耳钉都可以住～',
      '轻轻放进来，我会帮你看好～',
      '这一格留给最小的宝贝～',
    ],
    bowl: [
      '衣柜空空的，别急，第一件慢慢来～',
      '星星棒轻轻一挥，新衣服就会来～',
      '每一件喜欢的衣服，都值得被好好收好～',
    ],
    fly: [
      '咦？没找到，我再飞高一点看看～',
      '换个关键词，说不定它就藏在旁边～',
      '我绕了一圈，这里真的没有～',
    ],
    spoon: [
      '给衣柜换个口味？今天想加点什么料～',
      '搅一搅，蓝水彩味刚刚好～',
      '这锅外观汤，还能再撒点星星～',
    ],
    outfit: [
      '还没有搭配？……我勉强陪你搭一套',
      '衣服都在这儿了，动动手吧',
      '第一套就交给我……和黑猫监督',
    ],
    'outfit-filter': [
      '这套搭配飞去哪儿了？我找找～',
      '换个场景词，也许会冒出来～',
      '没看见这套，要不要清掉筛选？',
    ],
    recycle: [
      '回收站干干净净，大家都好好的～',
      '这里很安静，没有走丢的东西～',
      '空空的回收站，看着就安心～',
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
  let activeButton = null;
  let scrollFrame = null;

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
    activeButton = null;
    if (bubble) bubble.classList.remove('is-visible');
  }

  function positionBubble(button) {
    const el = ensureBubble();
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

    activeButton = button;
    positionBubble(button);
    requestAnimationFrame(() => el.classList.add('is-visible'));

    if (hideTimer) clearTimeout(hideTimer);
    hideTimer = window.setTimeout(() => {
      el.classList.remove('is-visible');
      activeButton = null;
      hideTimer = null;
    }, 2600);
  }

  function isButtonOnScreen(button) {
    if (!button || !button.isConnected) return false;
    const rect = button.getBoundingClientRect();
    return (
      rect.bottom > 0 &&
      rect.top < window.innerHeight &&
      rect.right > 0 &&
      rect.left < window.innerWidth
    );
  }

  function repositionBubble() {
    if (!bubble || !activeButton) return;
    if (!bubble.classList.contains('is-visible')) return;
    if (!isButtonOnScreen(activeButton)) {
      hideBubble();
      return;
    }
    positionBubble(activeButton);
  }

  function onScrollOrResize() {
    if (scrollFrame) return;
    scrollFrame = window.requestAnimationFrame(() => {
      scrollFrame = null;
      repositionBubble();
    });
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
    window.setTimeout(() => button.classList.remove('is-playing'), 820);

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
    // 捕获所有内部滚动容器（衣帽柜、设置页、左右栏）
    document.addEventListener('scroll', onScrollOrResize, true);
    window.addEventListener('resize', onScrollOrResize);
  }

  App.mascots = { init };
})(window.App = window.App || {});
