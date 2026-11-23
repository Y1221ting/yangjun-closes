/* 搭配上身展示：上传整套上身图，拖动旋转查看。 */
(function (App) {
  'use strict';

  const ANGLE_ORDER = ['front', 'front45', 'side', 'back135', 'back'];
  const state = { meta: null, outfit: null };
  const els = {};

  function cache() {
    els.title = document.getElementById('worn-title');
    els.count = document.getElementById('worn-count');
    els.view = document.getElementById('worn-view');
    els.empty = document.getElementById('worn-empty');
    els.list = document.getElementById('worn-angle-list');
  }

  function labelOf(angle) {
    const found = (state.meta.angles || []).find((opt) => opt.value === angle);
    return found ? found.label : angle;
  }

  function clampNumber(value, min, max, fallback) {
    const num = Number(value);
    if (!Number.isFinite(num)) return fallback;
    return Math.min(max, Math.max(min, num));
  }

  function version() {
    return state.outfit && state.outfit.updated_at
      ? `?v=${encodeURIComponent(state.outfit.updated_at)}`
      : '';
  }

  // ---------------------------------------------------------------- 上传

  function pickImage(angle, label) {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/png,image/jpeg,image/webp';

    input.addEventListener('change', async () => {
      const file = input.files && input.files[0] ? input.files[0] : null;
      if (!file) return;

      try {
        await App.api.upload(
          `/api/outfits/${state.outfit.id}/images?angle=${angle}`,
          file
        );
        App.ui.toast(`${label}上身图已保存`);
        state.outfit = await App.api.get(`/api/outfits/${state.outfit.id}`);
        render();
      } catch (err) {
        App.ui.toast(err.message, 'error');
      }
    });

    input.click();
  }

  // ---------------------------------------------------------------- 微调

  function saveAdjustment(angle, adjustment) {
    App.api
      .put(`/api/outfits/${state.outfit.id}/images/${angle}`, adjustment)
      .then((updated) => {
        state.outfit.images[angle] = {
          ...state.outfit.images[angle],
          ...updated,
        };
      })
      .catch((err) => App.ui.toast(err.message, 'error'));
  }

  function bindAdjust(angle, panel) {
    const sliders = Array.from(panel.querySelectorAll('input[type=range]'));
    let timer = 0;

    function readValues() {
      const result = { scale: 1, offset_x: 0, offset_y: 0 };
      sliders.forEach((slider) => {
        const num = Number(slider.value);
        if (slider.dataset.key === 'scale') {
          result.scale = num / 100;
        } else if (slider.dataset.key === 'offset_x') {
          result.offset_x = num;
        } else {
          result.offset_y = num;
        }
      });
      return result;
    }

    function onInput() {
      sliders.forEach((slider) => {
        const label = slider.parentElement.querySelector('em');
        if (label) label.textContent = `${slider.value}%`;
      });
      const adjustment = readValues();
      App.outfitWornView.setAdjustment(angle, adjustment);
      clearTimeout(timer);
      timer = setTimeout(() => saveAdjustment(angle, adjustment), 350);
    }

    sliders.forEach((slider) => slider.addEventListener('input', onInput));

    const reset = panel.querySelector('[data-action="reset"]');
    reset.addEventListener('click', () => {
      sliders.forEach((slider) => {
        slider.value = slider.dataset.key === 'scale' ? '100' : '0';
      });
      onInput();
    });
  }

  // ---------------------------------------------------------------- 渲染

  function renderAngles() {
    const images = state.outfit.images || {};
    const suffix = version();
    els.list.innerHTML = '';

    ANGLE_ORDER.forEach((angle) => {
      const image = images[angle] || null;
      const label = labelOf(angle);
      const scaleValue = Math.round(clampNumber(image && image.scale, 0.6, 1.4, 1) * 100);
      const offsetX = Math.round(clampNumber(image && image.offset_x, -30, 30, 0));
      const offsetY = Math.round(clampNumber(image && image.offset_y, -30, 30, 0));

      const row = document.createElement('div');
      row.className = 'angle-row';
      row.innerHTML = `
        <div class="angle-row__main">
          <div class="angle-row__thumb">
            ${image ? `<img src="/data/${App.ui.escapeHtml(image.path)}${suffix}" alt="${label}">` : ''}
          </div>
          <div class="angle-row__name">${label}</div>
          <span class="angle-row__state">${image ? '' : '未上传'}</span>
          <div class="angle-row__actions">
            ${image ? '<button class="btn btn--ghost" type="button" data-action="adjust">微调</button>' : ''}
            <button class="btn btn--ghost" type="button" data-action="upload">${image ? '替换' : '上传'}</button>
          </div>
        </div>
        ${
          image
            ? `
        <div class="angle-adjust" hidden>
          <label class="angle-adjust__row">
            <span>大小</span>
            <input type="range" min="60" max="140" step="1" value="${scaleValue}" data-key="scale">
            <em>${scaleValue}%</em>
          </label>
          <label class="angle-adjust__row">
            <span>上下</span>
            <input type="range" min="-30" max="30" step="1" value="${offsetY}" data-key="offset_y">
            <em>${offsetY}%</em>
          </label>
          <label class="angle-adjust__row">
            <span>左右</span>
            <input type="range" min="-30" max="30" step="1" value="${offsetX}" data-key="offset_x">
            <em>${offsetX}%</em>
          </label>
          <button class="btn btn--link" type="button" data-action="reset">恢复默认</button>
        </div>`
            : ''
        }
      `;

      row.querySelector('[data-action="upload"]').addEventListener('click', () => {
        pickImage(angle, label);
      });

      const adjustBtn = row.querySelector('[data-action="adjust"]');
      const panel = row.querySelector('.angle-adjust');
      if (adjustBtn && panel) {
        adjustBtn.addEventListener('click', () => {
          panel.hidden = !panel.hidden;
        });
        bindAdjust(angle, panel);
      }

      els.list.appendChild(row);
    });
  }

  function render() {
    const outfit = state.outfit;
    const angles = Object.keys(outfit.images || {});

    els.title.textContent = `${outfit.name} · 上身`;
    els.count.textContent = angles.length ? `${angles.length} 个角度` : '0 个角度';

    if (angles.length) {
      els.empty.hidden = true;
      App.outfitWornView.mount(outfit.images, outfit.updated_at);
    } else {
      els.empty.hidden = false;
      App.outfitWornView.mount({});
    }

    renderAngles();
  }

  // ---------------------------------------------------------------- 加载

  async function load(outfitId) {
    try {
      state.outfit = await App.api.get(`/api/outfits/${outfitId}`);
      render();
    } catch (err) {
      App.ui.toast(err.message, 'error');
      App.nav.toOutfits();
    }
  }

  function init(meta) {
    state.meta = meta;
    cache();
    document.getElementById('btn-worn-back').addEventListener('click', () => {
      if (state.outfit) {
        App.nav.toOutfit(state.outfit.id);
      } else {
        App.nav.toOutfits();
      }
    });
  }

  App.outfitWorn = { init, load };
})(window.App = window.App || {});
