/* 添加 / 编辑衣服抽屉：角度图、信息点选、草稿暂存、文件拖入上传。 */
(function (App) {
  'use strict';

  const ANGLE_ORDER = ['front', 'front45', 'side', 'back135', 'back'];
  // 拖入图片时优先填入这三个常用角度，再补 45° / 135°
  const FILL_ORDER = ['front', 'side', 'back', 'front45', 'back135'];

  const state = {
    meta: null,
    mode: 'create',
    garmentId: null,
    files: { front: null, front45: null, side: null, back135: null, back: null },
    category: '',
    color: '',
    displayStyle: 'hang',
    seasons: new Set(),
    occasions: new Set(),
    busy: false,
  };

  const els = {};
  const urls = [];
  let createDraft = null;

  function cache() {
    els.drawer = document.getElementById('drawer');
    els.form = document.getElementById('garment-form');
    els.title = document.getElementById('drawer-title');
    els.uploadHint = document.getElementById('upload-hint');
    els.name = document.getElementById('name-input');
    els.displayStyleField = document.getElementById('display-style-field');
    els.save = document.getElementById('btn-save');
    els.clearDraft = document.getElementById('btn-clear-draft');
    els.uploads = Array.from(document.querySelectorAll('.upload'));
    els.uploadsBox = document.querySelector('.uploads');
  }

  function tileOf(angle) {
    return els.uploads.find((tile) => tile.dataset.angle === angle);
  }

  // ---------------------------------------------------------------- 图片预览

  function setPreviewUrl(tile, url) {
    const preview = tile.querySelector('[data-preview]');
    if (url) {
      preview.style.backgroundImage = `url("${url}")`;
      preview.classList.add('has-image');
    } else {
      preview.style.backgroundImage = '';
      preview.classList.remove('has-image');
    }
  }

  function setFilePreview(tile, file) {
    if (!file) {
      setPreviewUrl(tile, null);
      return;
    }
    const url = URL.createObjectURL(file);
    urls.push(url);
    setPreviewUrl(tile, url);
  }

  function releaseUrls() {
    while (urls.length) {
      URL.revokeObjectURL(urls.pop());
    }
  }

  function bindUploads() {
    els.uploads.forEach((tile) => {
      const input = tile.querySelector('input[type=file]');
      input.addEventListener('change', () => {
        const file = input.files && input.files[0] ? input.files[0] : null;
        state.files[tile.dataset.angle] = file;
        setFilePreview(tile, file);
      });
    });
  }

  // ---------------------------------------------------------------- 拖入图片

  function hasFiles(event) {
    const types = event.dataTransfer && event.dataTransfer.types;
    return Boolean(types && Array.from(types).includes('Files'));
  }

  function handleFiles(files, preferredAngle) {
    const images = Array.from(files || []).filter((file) =>
      file.type.startsWith('image/')
    );
    if (!images.length) {
      App.ui.toast('请拖入图片文件（PNG / JPG）', 'error');
      return;
    }

    const order = [];
    if (preferredAngle) order.push(preferredAngle);
    FILL_ORDER.forEach((angle) => {
      if (!order.includes(angle)) order.push(angle);
    });

    images.slice(0, order.length).forEach((file, index) => {
      const angle = order[index];
      state.files[angle] = file;
      const tile = tileOf(angle);
      if (!tile) return;
      const input = tile.querySelector('input[type=file]');
      if (input) input.value = '';
      setFilePreview(tile, file);
    });

    if (images.length > order.length) {
      App.ui.toast(`最多填入 ${order.length} 个角度，多余的图片已忽略`);
    } else {
      App.ui.toast(`已填入 ${Math.min(images.length, order.length)} 张图片`);
    }
  }

  function bindDrop() {
    els.uploadsBox.addEventListener('dragover', (event) => {
      if (!hasFiles(event)) return;
      event.preventDefault();
      els.uploadsBox.classList.add('is-dragover');
    });
    els.uploadsBox.addEventListener('dragleave', () => {
      els.uploadsBox.classList.remove('is-dragover');
    });
    els.uploadsBox.addEventListener('drop', (event) => {
      if (!hasFiles(event)) return;
      event.preventDefault();
      event.stopPropagation();
      els.uploadsBox.classList.remove('is-dragover');
      handleFiles(event.dataTransfer.files, null);
    });

    els.uploads.forEach((tile) => {
      tile.addEventListener('dragover', (event) => {
        if (!hasFiles(event)) return;
        event.preventDefault();
        tile.classList.add('is-dragover');
      });
      tile.addEventListener('dragleave', () => {
        tile.classList.remove('is-dragover');
      });
      tile.addEventListener('drop', (event) => {
        if (!hasFiles(event)) return;
        event.preventDefault();
        event.stopPropagation();
        tile.classList.remove('is-dragover');
        handleFiles(event.dataTransfer.files, tile.dataset.angle);
      });
    });
  }

  function bindWindowDrop() {
    window.addEventListener('dragover', (event) => {
      if (hasFiles(event)) event.preventDefault();
    });
    window.addEventListener('drop', (event) => {
      if (!hasFiles(event)) return;
      event.preventDefault();
      if (document.querySelector('.modal')) return;

      if (els.drawer.hidden) {
        openCreate();
      }
      handleFiles(event.dataTransfer.files, null);
    });
  }

  // ---------------------------------------------------------------- 标签

  function toggleSet(set, value) {
    if (set.has(value)) {
      set.delete(value);
    } else {
      set.add(value);
    }
  }

  function isActive(key, value) {
    if (key === 'category') return state.category === value;
    if (key === 'color') return state.color === value;
    if (key === 'display_style') return state.displayStyle === value;
    if (key === 'season') return state.seasons.has(value);
    return state.occasions.has(value);
  }

  function updateDisplayStyleField() {
    if (els.displayStyleField) {
      els.displayStyleField.hidden = state.category !== 'accessory';
    }
  }

  function syncChips() {
    document.querySelectorAll('[data-chips]').forEach((container) => {
      const key = container.dataset.chips;
      container.querySelectorAll('.chip').forEach((btn) => {
        btn.classList.toggle('is-active', isActive(key, btn.dataset.value));
      });
    });
    updateDisplayStyleField();
  }

  function onChipClick(key, value) {
    if (key === 'category') {
      state.category = state.category === value ? '' : value;
    } else if (key === 'color') {
      state.color = state.color === value ? '' : value;
    } else if (key === 'display_style') {
      // 摆放方式必须三选一，点击已选项不取消
      state.displayStyle = value;
    } else if (key === 'season') {
      toggleSet(state.seasons, value);
    } else {
      toggleSet(state.occasions, value);
    }
    syncChips();
  }

  function renderChips() {
    const groups = [
      ['category', state.meta.categories],
      ['display_style', state.meta.display_styles || []],
      ['color', state.meta.colors],
      ['season', state.meta.seasons],
      ['occasion', state.meta.scenes.map((name) => ({ value: name, label: name }))],
    ];

    groups.forEach(([key, options]) => {
      const container = document.querySelector(`[data-chips="${key}"]`);
      container.innerHTML = '';
      options.forEach((opt) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'chip';
        btn.dataset.value = opt.value;
        btn.textContent = opt.label;
        btn.addEventListener('click', () => onChipClick(key, opt.value));
        container.appendChild(btn);
      });
    });
    syncChips();
  }

  // ---------------------------------------------------------------- 草稿

  function hasDraftContent() {
    return Boolean(
      Object.values(state.files).some(Boolean) ||
        els.name.value.trim() ||
        state.category ||
        state.color ||
        state.displayStyle !== 'hang' ||
        state.seasons.size ||
        state.occasions.size
    );
  }

  function captureDraft() {
    return {
      files: { ...state.files },
      name: els.name.value,
      category: state.category,
      color: state.color,
      displayStyle: state.displayStyle,
      seasons: Array.from(state.seasons),
      occasions: Array.from(state.occasions),
    };
  }

  function snapshotCreateDraft() {
    if (state.mode !== 'create') return;
    createDraft = hasDraftContent() ? captureDraft() : null;
  }

  function restoreDraft(draft) {
    resetFields();
    state.files = { ...draft.files };
    els.name.value = draft.name || '';
    state.category = draft.category || '';
    state.color = draft.color || '';
    state.displayStyle = draft.displayStyle || 'hang';
    state.seasons = new Set(draft.seasons || []);
    state.occasions = new Set(draft.occasions || []);

    ANGLE_ORDER.forEach((angle) => {
      const tile = tileOf(angle);
      if (tile) setFilePreview(tile, state.files[angle] || null);
    });
    syncChips();
  }

  function discardCreateDraft() {
    createDraft = null;
    resetFields();
  }

  // ---------------------------------------------------------------- 抽屉

  function resetFields() {
    state.mode = 'create';
    state.garmentId = null;
    state.files = { front: null, front45: null, side: null, back135: null, back: null };
    state.category = '';
    state.color = '';
    state.displayStyle = 'hang';
    state.seasons = new Set();
    state.occasions = new Set();

    els.form.reset();
    els.uploads.forEach((tile) => {
      tile.querySelector('input[type=file]').value = '';
      setPreviewUrl(tile, null);
    });
    syncChips();
    releaseUrls();
  }

  function openCreate() {
    if (createDraft) {
      restoreDraft(createDraft);
    } else {
      resetFields();
    }
    state.mode = 'create';
    state.garmentId = null;
    els.title.textContent = '添加衣服';
    els.uploadHint.textContent = '正面必填，其余角度可稍后补 · 可直接从文件夹拖入图片';
    els.clearDraft.hidden = false;
    els.drawer.hidden = false;
    els.name.focus();
  }

  function openEdit(garment) {
    snapshotCreateDraft();
    resetFields();
    state.mode = 'edit';
    state.garmentId = garment.id;
    state.category = garment.category || '';
    state.color = garment.color || '';
    state.displayStyle = garment.display_style || 'hang';
    state.seasons = new Set(garment.seasons || []);
    state.occasions = new Set(garment.occasions || []);

    els.title.textContent = '编辑衣服';
    els.uploadHint.textContent = '不重新选择就保留原图';
    els.clearDraft.hidden = true;
    els.name.value = garment.name;

    ANGLE_ORDER.forEach((angle) => {
      const image = garment.images && garment.images[angle];
      if (image && tileOf(angle)) {
        setPreviewUrl(tileOf(angle), `/data/${image.path}`);
      }
    });

    syncChips();
    els.drawer.hidden = false;
    els.name.focus();
  }

  function close(options) {
    const discard = Boolean(options && options.discard);

    if (discard) {
      if (state.mode === 'create') {
        createDraft = null;
        resetFields();
      }
    } else {
      snapshotCreateDraft();
      if (state.mode === 'create' && createDraft) {
        setTimeout(() => {
          App.ui.toast('已暂存，下次打开可以继续');
        }, 60);
      }
    }

    els.drawer.hidden = true;
    releaseUrls();
  }

  function setBusy(busy) {
    state.busy = busy;
    els.save.disabled = busy;
    els.save.textContent = busy ? '保存中…' : '保存';
  }

  // ---------------------------------------------------------------- 提交

  async function uploadSelected(garmentId) {
    for (const angle of ANGLE_ORDER) {
      const file = state.files[angle];
      if (!file) continue;
      await App.api.upload(`/api/garments/${garmentId}/images?angle=${angle}`, file);
    }
  }

  async function submit(event) {
    event.preventDefault();
    if (state.busy) return;

    const isEdit = state.mode === 'edit';
    const name = els.name.value.trim();

    if (!name) {
      App.ui.toast('请填写衣服名称', 'error');
      els.name.focus();
      return;
    }
    if (!state.category) {
      App.ui.toast('请选择衣服类别', 'error');
      return;
    }
    if (!isEdit && !state.files.front) {
      App.ui.toast('请先选择正面图', 'error');
      return;
    }

    setBusy(true);

    const payload = {
      name,
      category: state.category,
      color: state.color || null,
      display_style: state.displayStyle,
      seasons: Array.from(state.seasons),
      occasions: Array.from(state.occasions),
    };

    let garmentId = state.garmentId;

    try {
      if (isEdit) {
        await App.api.put(`/api/garments/${garmentId}`, payload);
      } else {
        const created = await App.api.post('/api/garments', payload);
        garmentId = created.id;
      }
      await uploadSelected(garmentId);
    } catch (err) {
      // 新建失败时把刚建的空衣服删掉，避免留下没有图片的记录
      if (!isEdit && garmentId) {
        try {
          await App.api.del(`/api/garments/${garmentId}`);
        } catch (ignore) {
          /* 删除失败不覆盖原始错误 */
        }
      }
      App.ui.toast(err.message || '保存失败，请重试', 'error');
      setBusy(false);
      return;
    }

    setBusy(false);
    close({ discard: !isEdit });
    App.ui.toast(isEdit ? '已保存' : '已添加到衣柜');
    App.wardrobe.load();
    if (isEdit && App.detail) {
      App.detail.load(garmentId);
    }
  }

  // ---------------------------------------------------------------- 初始化

  function init(meta) {
    state.meta = meta;
    cache();
    bindUploads();
    bindDrop();
    bindWindowDrop();
    renderChips();

    els.form.addEventListener('submit', submit);
    els.drawer.querySelectorAll('[data-close]').forEach((el) => {
      el.addEventListener('click', () => close());
    });
    els.clearDraft.addEventListener('click', () => {
      discardCreateDraft();
      App.ui.toast('已清空，可以重新填写');
    });
    document.getElementById('btn-add').addEventListener('click', openCreate);
    document.getElementById('btn-add-empty').addEventListener('click', openCreate);
  }

  App.garmentForm = { init, openCreate, openEdit, close, handleFiles };
})(window.App = window.App || {});
