/* 搭配编辑：衣柜抽屉、画布拖放、缩放、层次与自动保存。 */
(function (App) {
  'use strict';

  // 各类别在画布上的基准宽度（百分比）
  const BASE_WIDTH = {
    outer: 42,
    top: 38,
    dress: 42,
    bottom: 34,
    shoes: 20,
    bag: 16,
    accessory: 12,
  };

  // 各类别拖入画布时的默认位置
  const DEFAULT_POSITION = {
    outer: { x: 0.5, y: 0.3 },
    top: { x: 0.5, y: 0.34 },
    dress: { x: 0.5, y: 0.48 },
    bottom: { x: 0.5, y: 0.66 },
    shoes: { x: 0.5, y: 0.88 },
    bag: { x: 0.76, y: 0.56 },
    accessory: { x: 0.5, y: 0.18 },
  };

  const state = {
    meta: null,
    outfit: null,
    items: [],
    garments: [],
    selectedKey: null,
    keyword: '',
    keySeq: 0,
    saveTimer: 0,
    metaTimer: 0,
    canvasW: 0,
    canvasH: 0,
    scenes: [],
  };

  const els = {};

  function cache() {
    els.page = document.getElementById('page-outfit');
    els.canvas = document.getElementById('outfit-canvas');
    els.viewport = document.getElementById('canvas-viewport');
    els.name = document.getElementById('outfit-name');
    els.saveStatus = document.getElementById('save-status');
    els.search = document.getElementById('editor-search');
    els.garments = document.getElementById('editor-garments');
    els.scenes = document.getElementById('outfit-scenes');
    els.selectionPanel = document.getElementById('selection-panel');
    els.itemScale = document.getElementById('item-scale');
    els.itemScaleValue = document.getElementById('item-scale-value');
    els.itemRotation = document.getElementById('item-rotation');
    els.itemRotationValue = document.getElementById('item-rotation-value');
    els.itemClipTop = document.getElementById('item-clip-top');
    els.itemClipTopValue = document.getElementById('item-clip-top-value');
    els.itemClipBottom = document.getElementById('item-clip-bottom');
    els.itemClipBottomValue = document.getElementById('item-clip-bottom-value');
    els.deleteBtn = document.getElementById('btn-outfit-delete');
    els.exportBtn = document.getElementById('btn-export');
    els.wornBtn = document.getElementById('btn-worn');
  }

  function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
  }

  function nextKey() {
    state.keySeq += 1;
    return `i${state.keySeq}`;
  }

  function setStatus(text) {
    els.saveStatus.textContent = text;
  }

  // ---------------------------------------------------------------- 加载

  async function load(outfitId) {
    clearTimeout(state.saveTimer);
    clearTimeout(state.metaTimer);

    try {
      const [outfit, garments] = await Promise.all([
        App.api.get(`/api/outfits/${outfitId}`),
        App.api.get('/api/garments'),
      ]);

      state.outfit = outfit;
      state.garments = garments;
      state.items = (outfit.items.flat || []).map((item) => ({
        ...item,
        key: nextKey(),
      }));
      state.scenes = outfit.scenes || [];
      state.selectedKey = null;
      state.keyword = '';
      els.search.value = '';
      els.name.value = outfit.name;
      setStatus('已保存');

      renderScenes();
      renderGarments();
      resizeCanvas();
      renderCanvas();
      updateSelectionPanel();
    } catch (err) {
      App.ui.toast(err.message, 'error');
      App.nav.toOutfits();
    }
  }

  // ---------------------------------------------------------------- 左侧衣柜

  function renderGarments() {
    els.garments.innerHTML = '';
    const keyword = state.keyword.trim();
    const list = state.garments.filter(
      (garment) => !keyword || garment.name.includes(keyword)
    );

    if (!list.length) {
      const tip = document.createElement('p');
      tip.className = 'panel__hint';
      tip.textContent = state.garments.length ? '没有找到衣服' : '衣柜还是空的';
      els.garments.appendChild(tip);
      return;
    }

    list.forEach((garment) => {
      const row = document.createElement('button');
      row.type = 'button';
      row.className = 'editor-item';
      row.innerHTML = `
        <span class="editor-item__thumb">
          ${garment.thumb ? `<img src="/data/${App.ui.escapeHtml(garment.thumb)}" alt="">` : ''}
        </span>
        <span class="editor-item__name">${App.ui.escapeHtml(garment.name)}</span>
      `;
      row.addEventListener('click', () => addGarment(garment));
      els.garments.appendChild(row);
    });
  }

  function addGarment(garment) {
    const category = garment.category || 'top';
    const position = DEFAULT_POSITION[category] || DEFAULT_POSITION.top;
    const sameCategory = state.items.filter(
      (item) => item.garment.category === category
    ).length;
    const front = garment.images && garment.images.front;

    const item = {
      key: nextKey(),
      garment_id: garment.id,
      x: position.x,
      y: Math.min(0.95, position.y + sameCategory * 0.04),
      scale: 1,
      rotation: 0,
      z_index: state.items.length,
      locked: 0,
      clip_top: 0,
      clip_bottom: 1,
      garment: {
        name: garment.name,
        category,
        image: front ? front.path : garment.thumb,
      },
    };

    state.items.push(item);
    selectItem(item.key);
    renderCanvas();
    scheduleSave();
  }

  // ---------------------------------------------------------------- 画布

  function resizeCanvas() {
    const rect = els.viewport.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    const scale = Math.min((rect.width - 8) / 1200, (rect.height - 8) / 1600);
    const width = Math.max(200, Math.floor(1200 * scale));
    const height = Math.max(266, Math.floor(1600 * scale));
    els.canvas.style.width = `${width}px`;
    els.canvas.style.height = `${height}px`;
    state.canvasW = width;
    state.canvasH = height;
  }

  function clipStyle(item) {
    const top = typeof item.clip_top === 'number' ? item.clip_top : 0;
    const bottom = typeof item.clip_bottom === 'number' ? item.clip_bottom : 1;
    return `inset(${(top * 100).toFixed(2)}% 0 ${((1 - bottom) * 100).toFixed(2)}% 0)`;
  }

  function renderCanvas() {
    els.canvas.innerHTML = '';

    state.items.forEach((item) => {
      const el = document.createElement('div');
      el.className =
        'canvas-item' + (item.key === state.selectedKey ? ' is-selected' : '');
      el.dataset.key = item.key;
      el.style.left = `${item.x * 100}%`;
      el.style.top = `${item.y * 100}%`;
      el.style.width = `${(BASE_WIDTH[item.garment.category] || 30) * item.scale}%`;
      el.style.zIndex = String(item.z_index);
      el.style.transform = `translate(-50%, -50%) rotate(${item.rotation}deg)`;

      const img = document.createElement('img');
      img.src = `/data/${item.garment.image}`;
      img.alt = item.garment.name;
      img.draggable = false;
      img.style.clipPath = clipStyle(item);
      el.appendChild(img);

      bindItemDrag(el, item);
      els.canvas.appendChild(el);
    });
  }

  function updateItemElement(item) {
    const el = els.canvas.querySelector(`[data-key="${item.key}"]`);
    if (!el) return;
    el.style.left = `${item.x * 100}%`;
    el.style.top = `${item.y * 100}%`;
    el.style.width = `${(BASE_WIDTH[item.garment.category] || 30) * item.scale}%`;
    el.style.zIndex = String(item.z_index);
    el.style.transform = `translate(-50%, -50%) rotate(${item.rotation}deg)`;
    const img = el.querySelector('img');
    if (img) img.style.clipPath = clipStyle(item);
  }

  function bindItemDrag(el, item) {
    el.addEventListener('pointerdown', (event) => {
      if (event.button !== undefined && event.button !== 0) return;
      event.stopPropagation();
      selectItem(item.key);

      if (!state.canvasW || !state.canvasH) resizeCanvas();

      const startX = event.clientX;
      const startY = event.clientY;
      const originX = item.x;
      const originY = item.y;
      let moved = false;

      el.setPointerCapture(event.pointerId);
      el.classList.add('is-dragging');

      function onMove(moveEvent) {
        const dx = (moveEvent.clientX - startX) / state.canvasW;
        const dy = (moveEvent.clientY - startY) / state.canvasH;
        if (Math.abs(dx) + Math.abs(dy) > 0.003) moved = true;
        item.x = clamp(originX + dx, 0, 1);
        item.y = clamp(originY + dy, 0, 1);
        el.style.left = `${item.x * 100}%`;
        el.style.top = `${item.y * 100}%`;
      }

      function onUp(upEvent) {
        el.removeEventListener('pointermove', onMove);
        el.removeEventListener('pointerup', onUp);
        el.removeEventListener('pointercancel', onUp);
        try {
          el.releasePointerCapture(upEvent.pointerId);
        } catch (ignore) {
          /* 已释放时忽略 */
        }
        el.classList.remove('is-dragging');
        if (moved) scheduleSave();
      }

      el.addEventListener('pointermove', onMove);
      el.addEventListener('pointerup', onUp);
      el.addEventListener('pointercancel', onUp);
    });
  }

  // ---------------------------------------------------------------- 选中

  function selectedItem() {
    return state.items.find((item) => item.key === state.selectedKey) || null;
  }

  function selectItem(key) {
    state.selectedKey = key;
    els.canvas.querySelectorAll('.canvas-item').forEach((el) => {
      el.classList.toggle('is-selected', el.dataset.key === key);
    });
    updateSelectionPanel();
  }

  function updateSelectionPanel() {
    const item = selectedItem();
    els.selectionPanel.hidden = !item;
    if (!item) return;

    els.itemScale.value = String(Math.round(item.scale * 100));
    els.itemScaleValue.textContent = `${Math.round(item.scale * 100)}%`;
    els.itemRotation.value = String(Math.round(item.rotation));
    els.itemRotationValue.textContent = `${Math.round(item.rotation)}°`;

    const clipTop = Math.round((item.clip_top || 0) * 100);
    const clipBottom = Math.round(
      (typeof item.clip_bottom === 'number' ? item.clip_bottom : 1) * 100
    );
    els.itemClipTop.value = String(clipTop);
    els.itemClipTopValue.textContent = `${clipTop}%`;
    els.itemClipBottom.value = String(clipBottom);
    els.itemClipBottomValue.textContent = `${clipBottom}%`;
  }

  function layerMove(mode) {
    const item = selectedItem();
    if (!item) return;

    const sorted = state.items.slice().sort((a, b) => a.z_index - b.z_index);
    const index = sorted.indexOf(item);
    if (index < 0) return;

    if (mode === 'top') {
      sorted.splice(index, 1);
      sorted.push(item);
    } else if (mode === 'bottom') {
      sorted.splice(index, 1);
      sorted.unshift(item);
    } else if (mode === 'up' && index < sorted.length - 1) {
      const next = sorted[index + 1];
      sorted[index + 1] = item;
      sorted[index] = next;
    } else if (mode === 'down' && index > 0) {
      const prev = sorted[index - 1];
      sorted[index - 1] = item;
      sorted[index] = prev;
    } else {
      return;
    }

    sorted.forEach((entry, zIndex) => {
      entry.z_index = zIndex;
    });
    renderCanvas();
    scheduleSave();
  }

  async function deleteSelected() {
    const item = selectedItem();
    if (!item) return;

    const confirmed = await App.ui.confirm({
      title: `从搭配中移除「${item.garment.name}」？`,
      message: '只会从这套搭配里移除，衣柜里的原图不会删除。',
      confirmText: '移除',
    });
    if (!confirmed) return;

    state.items = state.items.filter((entry) => entry !== item);
    state.selectedKey = null;
    state.items.forEach((entry, index) => {
      entry.z_index = index;
    });
    renderCanvas();
    updateSelectionPanel();
    scheduleSave();
  }

  // ---------------------------------------------------------------- 保存

  function scheduleSave() {
    setStatus('保存中…');
    clearTimeout(state.saveTimer);
    state.saveTimer = setTimeout(saveItems, 800);
  }

  async function saveItems() {
    const payload = {
      items: state.items.map((item) => ({
        garment_id: item.garment_id,
        view: 'flat',
        x: item.x,
        y: item.y,
        scale: item.scale,
        rotation: item.rotation,
        z_index: item.z_index,
        locked: item.locked ? 1 : 0,
        clip_top: item.clip_top || 0,
        clip_bottom: typeof item.clip_bottom === 'number' ? item.clip_bottom : 1,
      })),
    };

    try {
      await App.api.put(
        `/api/outfits/${state.outfit.id}/items?view=flat`,
        payload
      );
      setStatus('已保存');
    } catch (err) {
      setStatus('保存失败');
      App.ui.toast(err.message, 'error');
    }
  }

  function scheduleMetaSave() {
    clearTimeout(state.metaTimer);
    state.metaTimer = setTimeout(saveMeta, 600);
  }

  async function saveMeta() {
    const name = els.name.value.trim() || '未命名搭配';
    try {
      const updated = await App.api.put(`/api/outfits/${state.outfit.id}`, {
        name,
        scenes: state.scenes,
      });
      state.outfit.name = updated.name;
      state.outfit.scenes = updated.scenes;
      setStatus('已保存');
    } catch (err) {
      setStatus('保存失败');
      App.ui.toast(err.message, 'error');
    }
  }

  // ---------------------------------------------------------------- 场景

  function renderScenes() {
    els.scenes.innerHTML = '';
    (state.meta.scenes || []).forEach((name) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'chip' + (state.scenes.includes(name) ? ' is-active' : '');
      btn.textContent = name;
      btn.addEventListener('click', () => {
        if (state.scenes.includes(name)) {
          state.scenes = state.scenes.filter((scene) => scene !== name);
        } else {
          state.scenes.push(name);
        }
        renderScenes();
        scheduleMetaSave();
      });
      els.scenes.appendChild(btn);
    });
  }

  // ---------------------------------------------------------------- 删除搭配

  async function onDeleteOutfit() {
    const outfit = state.outfit;
    if (!outfit) return;

    const confirmed = await App.ui.confirm({
      title: `删除搭配「${outfit.name}」？`,
      message: '这套搭配会移入回收站，布局和上身图都会保留，可以随时恢复。',
      confirmText: '移入回收站',
    });
    if (!confirmed) return;

    try {
      await App.api.del(`/api/outfits/${outfit.id}`);
      App.ui.toast('已删除搭配');
      App.nav.toOutfits();
    } catch (err) {
      App.ui.toast(err.message, 'error');
    }
  }

  // ---------------------------------------------------------------- 导出

  function loadImage(src) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = () => reject(new Error('图片加载失败'));
      img.src = src;
    });
  }

  async function exportOutfit() {
    if (!state.outfit) return;
    if (!state.items.length) {
      App.ui.toast('画布是空的，先添加衣服', 'error');
      return;
    }

    els.exportBtn.disabled = true;
    els.exportBtn.textContent = '导出中…';

    try {
      const stamp = Date.now();
      const loaded = [];
      for (const item of state.items) {
        const img = await loadImage(`/data/${item.garment.image}?v=${stamp}`);
        loaded.push({ item, img });
      }

      const canvas = document.createElement('canvas');
      canvas.width = 1200;
      canvas.height = 1600;
      const ctx = canvas.getContext('2d');
      ctx.fillStyle = '#FFFFFF';
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      loaded
        .sort((a, b) => a.item.z_index - b.item.z_index)
        .forEach(({ item, img }) => {
          const category = item.garment.category;
          const width =
            ((BASE_WIDTH[category] || 30) / 100) * canvas.width * item.scale;
          const height = width * (img.naturalHeight / img.naturalWidth);
          const clipTop = typeof item.clip_top === 'number' ? item.clip_top : 0;
          const clipBottom =
            typeof item.clip_bottom === 'number' ? item.clip_bottom : 1;
          const clipHeight = Math.max(0, (clipBottom - clipTop) * height);
          if (clipHeight <= 0) return;

          ctx.save();
          ctx.translate(item.x * canvas.width, item.y * canvas.height);
          ctx.rotate((item.rotation * Math.PI) / 180);
          ctx.beginPath();
          ctx.rect(
            -width / 2,
            -height / 2 + clipTop * height,
            width,
            clipHeight
          );
          ctx.clip();
          ctx.drawImage(img, -width / 2, -height / 2, width, height);
          ctx.restore();
        });

      const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/png'));
      if (!blob) throw new Error('生成图片失败');

      const name = els.name.value.trim() || '搭配';
      const result = await App.api.upload(
        `/api/export?name=${encodeURIComponent(name)}`,
        blob
      );
      App.ui.toast(`已导出：${result.name}`);

      try {
        await App.api.post('/api/exports/open');
      } catch (ignore) {
        /* 打不开文件夹不影响导出结果 */
      }
    } catch (err) {
      App.ui.toast(err.message || '导出失败', 'error');
    } finally {
      els.exportBtn.disabled = false;
      els.exportBtn.textContent = '导出图片';
    }
  }

  // ---------------------------------------------------------------- 初始化

  function init(meta) {
    state.meta = meta;
    cache();

    document
      .getElementById('btn-outfit-back')
      .addEventListener('click', () => App.nav.toOutfits());
    els.deleteBtn.addEventListener('click', onDeleteOutfit);
    els.exportBtn.addEventListener('click', exportOutfit);
    els.wornBtn.addEventListener('click', () => {
      if (state.outfit) {
        App.nav.toOutfitWorn(state.outfit.id);
      }
    });

    els.search.addEventListener('input', () => {
      state.keyword = els.search.value;
      renderGarments();
    });

    els.itemScale.addEventListener('input', () => {
      const item = selectedItem();
      if (!item) return;
      item.scale = clamp(Number(els.itemScale.value) / 100, 0.2, 3);
      els.itemScaleValue.textContent = `${els.itemScale.value}%`;
      updateItemElement(item);
      scheduleSave();
    });

    els.itemRotation.addEventListener('input', () => {
      const item = selectedItem();
      if (!item) return;
      item.rotation = Number(els.itemRotation.value);
      els.itemRotationValue.textContent = `${els.itemRotation.value}°`;
      updateItemElement(item);
      scheduleSave();
    });

    function onClipInput() {
      const item = selectedItem();
      if (!item) return;

      let clipTop = Number(els.itemClipTop.value);
      let clipBottom = Number(els.itemClipBottom.value);
      if (clipBottom < clipTop) {
        if (document.activeElement === els.itemClipTop) {
          clipTop = clipBottom;
        } else {
          clipBottom = clipTop;
        }
      }

      item.clip_top = clipTop / 100;
      item.clip_bottom = clipBottom / 100;
      els.itemClipTop.value = String(clipTop);
      els.itemClipBottom.value = String(clipBottom);
      els.itemClipTopValue.textContent = `${clipTop}%`;
      els.itemClipBottomValue.textContent = `${clipBottom}%`;
      updateItemElement(item);
      scheduleSave();
    }

    els.itemClipTop.addEventListener('input', onClipInput);
    els.itemClipBottom.addEventListener('input', onClipInput);

    document
      .getElementById('btn-layer-top')
      .addEventListener('click', () => layerMove('top'));
    document
      .getElementById('btn-layer-bottom')
      .addEventListener('click', () => layerMove('bottom'));
    document
      .getElementById('btn-layer-up')
      .addEventListener('click', () => layerMove('up'));
    document
      .getElementById('btn-layer-down')
      .addEventListener('click', () => layerMove('down'));
    document
      .getElementById('btn-item-delete')
      .addEventListener('click', deleteSelected);

    els.canvas.addEventListener('pointerdown', (event) => {
      if (event.target === els.canvas) {
        selectItem(null);
      }
    });

    els.canvas.addEventListener(
      'wheel',
      (event) => {
        event.preventDefault();
        const target = event.target.closest('.canvas-item');
        const item = target
          ? state.items.find((entry) => entry.key === target.dataset.key)
          : selectedItem();
        if (!item) return;

        selectItem(item.key);
        const rect = els.canvas.getBoundingClientRect();
        const pointerX = (event.clientX - rect.left) / rect.width;
        const pointerY = (event.clientY - rect.top) / rect.height;
        const factor = event.deltaY < 0 ? 1.08 : 0.92;
        const nextScale = clamp(item.scale * factor, 0.2, 3);
        if (Math.abs(nextScale - item.scale) < 1e-4) return;

        const ratio = nextScale / item.scale;
        item.x = clamp(pointerX + (item.x - pointerX) * ratio, 0, 1);
        item.y = clamp(pointerY + (item.y - pointerY) * ratio, 0, 1);
        item.scale = nextScale;
        updateItemElement(item);
        updateSelectionPanel();
        scheduleSave();
      },
      { passive: false }
    );

    els.name.addEventListener('input', scheduleMetaSave);
    els.name.addEventListener('blur', () => {
      clearTimeout(state.metaTimer);
      saveMeta();
    });

    window.addEventListener('resize', () => {
      if (!els.page.hidden) resizeCanvas();
    });

    document.addEventListener('keydown', (event) => {
      if (els.page.hidden) return;
      const tag = document.activeElement ? document.activeElement.tagName : '';
      if (tag === 'INPUT' || tag === 'TEXTAREA') return;
      if ((event.key === 'Delete' || event.key === 'Backspace') && selectedItem()) {
        event.preventDefault();
        deleteSelected();
      }
    });
  }

  App.outfitEditor = { init, load };
})(window.App = window.App || {});
