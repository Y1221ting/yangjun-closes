/* 可复用的角度旋转视图：按住左右拖动，在正 / 45° / 侧 / 135° / 背之间翻卡切换。
   通过 createRotateView 创建多个实例（单品详情、搭配上身图各一个）。 */
(function (App) {
  'use strict';

  const ORDER = ['front', 'front45', 'side', 'back135', 'back'];
  const LABELS = {
    front: '正面',
    front45: '左前 45°',
    side: '侧面',
    back135: '左后 135°',
    back: '背面',
  };

  function createRotateView(ids) {
    const state = {
      frames: [],
      angle: 0,
      maxAngle: 180,
      dragging: false,
      startX: 0,
      startAngle: 0,
      dragRaf: 0,
      animRaf: 0,
      hasDragged: false,
    };

    const els = {};

    function cache() {
      els.view = document.getElementById(ids.view);
      els.frame = document.getElementById(ids.frame);
      els.dots = document.getElementById(ids.dots);
      els.hint = document.getElementById(ids.hint);
    }

    function clamp(value, min, max) {
      return Math.min(max, Math.max(min, value));
    }

    // ---------------------------------------------------------------- 渲染

    function render() {
      const styles = App.rotateMath.sample(state.frames, state.angle);
      state.frames.forEach((frame, index) => {
        const style = styles[index];
        const adjust = frame.adjust || { scale: 1, offsetX: 0, offsetY: 0 };
        frame.el.style.transform =
          `translate(${adjust.offsetX.toFixed(2)}%, ${adjust.offsetY.toFixed(2)}%) ` +
          `rotateY(${style.rotateY.toFixed(2)}deg) ` +
          `scaleX(${style.scaleX.toFixed(3)}) scale(${adjust.scale.toFixed(3)})`;
        frame.el.style.opacity = style.opacity.toFixed(3);
      });
      updateDots();
    }

    function updateDots() {
      if (!state.frames.length) return;
      let nearest = 0;
      state.frames.forEach((frame, index) => {
        if (
          Math.abs(frame.ideal - state.angle) <
          Math.abs(state.frames[nearest].ideal - state.angle)
        ) {
          nearest = index;
        }
      });
      els.dots.querySelectorAll('.rotate-view__dot').forEach((dot, index) => {
        dot.classList.toggle('is-active', index === nearest);
      });
    }

    function scheduleRender() {
      if (state.dragRaf) return;
      state.dragRaf = requestAnimationFrame(() => {
        state.dragRaf = 0;
        render();
      });
    }

    // ---------------------------------------------------------------- 拖动

    function onPointerDown(event) {
      if (state.frames.length < 2) return;
      if (event.target.closest('.rotate-view__dot')) return;
      if (event.button !== undefined && event.button !== 0) return;

      cancelAnimation();
      state.dragging = true;
      state.startX = event.clientX;
      state.startAngle = state.angle;
      els.view.classList.add('is-dragging');
      els.view.setPointerCapture(event.pointerId);

      if (!state.hasDragged) {
        state.hasDragged = true;
        els.hint.classList.add('is-faded');
      }
    }

    function onPointerMove(event) {
      if (!state.dragging) return;
      const delta = (event.clientX - state.startX) * 0.6;
      state.angle = clamp(state.startAngle + delta, 0, state.maxAngle);
      scheduleRender();
    }

    function onPointerUp(event) {
      if (!state.dragging) return;
      state.dragging = false;
      els.view.classList.remove('is-dragging');
      try {
        els.view.releasePointerCapture(event.pointerId);
      } catch (ignore) {
        /* 指针已经释放时忽略 */
      }
    }

    // ---------------------------------------------------------------- 动画

    function cancelAnimation() {
      if (state.animRaf) {
        cancelAnimationFrame(state.animRaf);
        state.animRaf = 0;
      }
    }

    function animateTo(target, duration) {
      cancelAnimation();
      const from = state.angle;
      const start = performance.now();
      const span = duration || 260;

      function step(now) {
        const t = Math.min(1, (now - start) / span);
        const eased = 1 - Math.pow(1 - t, 3);
        state.angle = from + (target - from) * eased;
        render();
        if (t < 1) {
          state.animRaf = requestAnimationFrame(step);
        } else {
          state.animRaf = 0;
        }
      }

      state.animRaf = requestAnimationFrame(step);
    }

    function onDoubleClick() {
      if (state.frames.length >= 2) {
        animateTo(0);
      }
    }

    // ---------------------------------------------------------------- 挂载

    function buildDots() {
      els.dots.innerHTML = '';
      state.frames.forEach((frame) => {
        const dot = document.createElement('button');
        dot.type = 'button';
        dot.className = 'rotate-view__dot';
        dot.title = LABELS[frame.angle] || frame.angle;
        dot.addEventListener('click', () => animateTo(frame.ideal));
        els.dots.appendChild(dot);
      });
    }

    function destroy() {
      cancelAnimation();
      if (state.dragRaf) {
        cancelAnimationFrame(state.dragRaf);
        state.dragRaf = 0;
      }
      state.dragging = false;
      state.frames = [];
      els.frame.innerHTML = '';
      els.dots.innerHTML = '';
    }

    function mount(images, version, options) {
      const previousAngle = state.angle;
      destroy();

      const angles = ORDER.filter((angle) => images && images[angle]);
      if (!angles.length) {
        els.view.hidden = true;
        return;
      }

      state.frames = App.rotateMath.buildFrames(angles).map((frame) => {
        const data = images[frame.angle];
        return {
          ...frame,
          adjust: {
            scale: typeof data.scale === 'number' ? data.scale : 1,
            offsetX: typeof data.offset_x === 'number' ? data.offset_x : 0,
            offsetY: typeof data.offset_y === 'number' ? data.offset_y : 0,
          },
        };
      });
      state.maxAngle = state.frames[state.frames.length - 1].ideal;
      state.angle =
        options && options.keepAngle ? Math.min(previousAngle, state.maxAngle) : 0;
      state.hasDragged = state.angle > 0;

      const suffix = version ? `?v=${encodeURIComponent(version)}` : '';

      els.frame.innerHTML = '';
      state.frames.forEach((frame) => {
        const img = document.createElement('img');
        img.className = 'rotate-view__img';
        img.alt = LABELS[frame.angle] || frame.angle;
        img.draggable = false;
        img.src = `/data/${images[frame.angle].path}${suffix}`;
        els.frame.appendChild(img);
        frame.el = img;
      });

      buildDots();
      els.dots.hidden = angles.length < 2;
      els.hint.textContent =
        angles.length >= 2
          ? '按住左右拖动查看其他角度 · 双击回正'
          : '只有一张图，上传其他角度后可以转动查看';
      els.hint.classList.remove('is-faded');
      els.view.classList.remove('is-dragging');
      els.view.hidden = false;
      render();
    }

    function setAdjustment(angle, adjustment) {
      const frame = state.frames.find((item) => item.angle === angle);
      if (!frame) return;
      frame.adjust = {
        scale: adjustment.scale,
        offsetX: adjustment.offset_x,
        offsetY: adjustment.offset_y,
      };
      render();
    }

    function init() {
      cache();
      els.view.addEventListener('pointerdown', onPointerDown);
      window.addEventListener('pointermove', onPointerMove);
      window.addEventListener('pointerup', onPointerUp);
      window.addEventListener('pointercancel', onPointerUp);
      els.view.addEventListener('dblclick', onDoubleClick);
    }

    return { init, mount, destroy, setAdjustment };
  }

  App.createRotateView = createRotateView;
  App.rotateView = createRotateView({
    view: 'rotate-view',
    frame: 'rotate-frame',
    dots: 'rotate-dots',
    hint: 'rotate-hint',
  });
  App.outfitWornView = createRotateView({
    view: 'worn-view',
    frame: 'worn-frame',
    dots: 'worn-dots',
    hint: 'worn-hint',
  });
})(window.App = window.App || {});
