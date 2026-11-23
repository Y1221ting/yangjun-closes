/* 衣服详情页：大图展示、信息、角度图替换、编辑与删除。 */
(function (App) {
  'use strict';

  const ANGLE_ORDER = ['front', 'front45', 'side', 'back135', 'back'];
  const state = { meta: null, garment: null };
  const els = {};
  let keepAngleOnNextMount = false;

  function cache() {
    els.page = document.getElementById('page-garment');
    els.drawer = document.getElementById('drawer');
    els.name = document.getElementById('detail-name');
    els.placeholder = document.getElementById('detail-placeholder');
    els.info = document.getElementById('detail-info');
    els.angles = document.getElementById('angle-list');
    els.deleteBtn = document.getElementById('btn-delete-garment');
    els.editBtn = document.getElementById('btn-edit');
    els.backBtn = document.getElementById('btn-back');
  }

  function labelOf(key, value) {
    const found = (state.meta[key] || []).find((opt) => opt.value === value);
    return found ? found.label : value || '—';
  }

  // ---------------------------------------------------------------- 渲染

  function renderInfo(garment) {
    const rows = [
      ['类别', labelOf('categories', garment.category)],
      ['颜色', garment.color ? labelOf('colors', garment.color) : '—'],
      [
        '季节',
        garment.seasons.length
          ? garment.seasons.map((item) => labelOf('seasons', item)).join(' / ')
          : '—',
      ],
      ['场合', garment.occasions.length ? garment.occasions.join(' / ') : '—'],
      ['添加时间', garment.created_at || '—'],
    ];

    els.info.innerHTML = rows
      .map(
        ([label, value]) => `
        <div class="info-row">
          <span class="info-row__label">${label}</span>
          <span class="info-row__value">${App.ui.escapeHtml(value)}</span>
        </div>`
      )
      .join('');
  }

  function clampNumber(value, min, max, fallback) {
    const num = Number(value);
    if (!Number.isFinite(num)) return fallback;
    return Math.min(max, Math.max(min, num));
  }

  function saveAdjustment(angle, adjustment) {
    App.api
      .put(`/api/garments/${state.garment.id}/images/${angle}`, adjustment)
      .then((updated) => {
        state.garment.images[angle] = {
          ...state.garment.images[angle],
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

    function updateLabels() {
      sliders.forEach((slider) => {
        const label = slider.parentElement.querySelector('em');
        if (label) label.textContent = `${slider.value}%`;
      });
    }

    function onInput() {
      updateLabels();
      const adjustment = readValues();
      App.rotateView.setAdjustment(angle, adjustment);
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

  function renderAngles(garment) {
    els.angles.innerHTML = '';
    const version = garment.updated_at
      ? `?v=${encodeURIComponent(garment.updated_at)}`
      : '';

    ANGLE_ORDER.forEach((angle) => {
      const angleMeta = (state.meta.angles || []).find((opt) => opt.value === angle);
      const label = angleMeta ? angleMeta.label : angle;
      const image = garment.images[angle] || null;

      const scaleValue = Math.round(
        clampNumber(image && image.scale, 0.6, 1.4, 1) * 100
      );
      const offsetX = Math.round(clampNumber(image && image.offset_x, -30, 30, 0));
      const offsetY = Math.round(clampNumber(image && image.offset_y, -30, 30, 0));

      const row = document.createElement('div');
      row.className = 'angle-row';
      row.innerHTML = `
        <div class="angle-row__main">
          <div class="angle-row__thumb">
            ${image ? `<img src="/data/${App.ui.escapeHtml(image.path)}${version}" alt="${label}">` : ''}
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

      els.angles.appendChild(row);
    });
  }

  function render() {
    const garment = state.garment;
    els.name.textContent = garment.name;
    els.name.title = garment.name;

    const hasImages = Object.keys(garment.images).length > 0;
    els.placeholder.hidden = hasImages;
    App.rotateView.mount(garment.images, garment.updated_at, {
      keepAngle: keepAngleOnNextMount,
    });
    keepAngleOnNextMount = false;

    renderInfo(garment);
    renderAngles(garment);
  }

  // ---------------------------------------------------------------- 上传角度图

  function pickImage(angle, label) {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/png,image/webp';

    input.addEventListener('change', async () => {
      const file = input.files && input.files[0] ? input.files[0] : null;
      if (!file) return;

      try {
        await App.api.upload(
          `/api/garments/${state.garment.id}/images?angle=${angle}`,
          file
        );
        App.ui.toast(`${label}图已更新`);
        keepAngleOnNextMount = true;
        await load(state.garment.id);
        App.wardrobe.load();
      } catch (err) {
        App.ui.toast(err.message, 'error');
      }
    });

    input.click();
  }

  // ---------------------------------------------------------------- 删除

  async function onDelete() {
    const garment = state.garment;
    if (!garment) return;

    const confirmed = await App.ui.confirm({
      title: `删除「${garment.name}」？`,
      message: '这件衣服会移入回收站，图片不会立刻删除，可以随时恢复。',
      confirmText: '移入回收站',
    });
    if (!confirmed) return;

    try {
      await App.api.del(`/api/garments/${garment.id}`);
      App.ui.toast('已删除');
      App.nav.toWardrobe();
      App.wardrobe.load();
    } catch (err) {
      App.ui.toast(err.message, 'error');
    }
  }

  // ---------------------------------------------------------------- 加载

  async function load(garmentId) {
    try {
      state.garment = await App.api.get(`/api/garments/${garmentId}`);
      render();
    } catch (err) {
      App.ui.toast(err.message, 'error');
      App.nav.toWardrobe();
    }
  }

  function init(meta) {
    state.meta = meta;
    cache();

    els.backBtn.addEventListener('click', () => App.nav.toWardrobe());
    els.editBtn.addEventListener('click', () => {
      if (state.garment) {
        App.garmentForm.openEdit(state.garment);
      }
    });
    els.deleteBtn.addEventListener('click', onDelete);

    document.addEventListener('keydown', (event) => {
      if (
        event.key === 'Escape' &&
        !els.page.hidden &&
        els.drawer.hidden
      ) {
        App.nav.toWardrobe();
      }
    });
  }

  App.detail = { init, load };
})(window.App = window.App || {});
