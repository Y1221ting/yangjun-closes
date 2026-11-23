/* 设置页：数据备份与回收站。 */
(function (App) {
  'use strict';

  const state = { data: null };
  const els = {};

  function cache() {
    els.garments = document.getElementById('trash-garments');
    els.outfits = document.getElementById('trash-outfits');
    els.garmentCount = document.getElementById('trash-garment-count');
    els.outfitCount = document.getElementById('trash-outfit-count');
    els.backupInfo = document.getElementById('backup-info');
    els.backupBtn = document.getElementById('btn-backup');
    els.welcomeToggle = document.getElementById('welcome-toggle');
  }

  function formatSize(bytes) {
    if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
    if (bytes >= 1024) return `${Math.round(bytes / 1024)} KB`;
    return `${bytes} B`;
  }

  function emptyHint(text) {
    const p = document.createElement('p');
    p.className = 'settings__empty';
    p.textContent = text;
    return p;
  }

  // ---------------------------------------------------------------- 回收站

  function renderGarments(items) {
    els.garmentCount.textContent = items.length ? `(${items.length})` : '';
    els.garments.innerHTML = '';

    if (!items.length) {
      els.garments.appendChild(emptyHint('回收站里没有衣服'));
      return;
    }

    items.forEach((item) => {
      const row = document.createElement('div');
      row.className = 'trash-row';
      const thumb = item.thumb
        ? `<img src="/data/${App.ui.escapeHtml(item.thumb)}" alt="">`
        : '<span class="trash-row__empty">无图</span>';
      row.innerHTML = `
        <div class="trash-row__thumb">${thumb}</div>
        <div class="trash-row__info">
          <p class="trash-row__name">${App.ui.escapeHtml(item.name)}</p>
          <p class="trash-row__meta">删除于 ${App.ui.escapeHtml(item.deleted_at || '')}</p>
        </div>
        <div class="trash-row__actions">
          <button class="btn btn--ghost" type="button" data-action="restore">恢复</button>
          <button class="btn btn--ghost btn--danger" type="button" data-action="purge">彻底删除</button>
        </div>
      `;
      row.querySelector('[data-action="restore"]').addEventListener('click', () => {
        restore('garments', item);
      });
      row.querySelector('[data-action="purge"]').addEventListener('click', () => {
        purge('garments', item);
      });
      els.garments.appendChild(row);
    });
  }

  function renderOutfits(items) {
    els.outfitCount.textContent = items.length ? `(${items.length})` : '';
    els.outfits.innerHTML = '';

    if (!items.length) {
      els.outfits.appendChild(emptyHint('回收站里没有搭配'));
      return;
    }

    items.forEach((item) => {
      const row = document.createElement('div');
      row.className = 'trash-row';
      const cover = item.worn_cover || item.cover;
      const thumb = cover
        ? `<img src="/data/${App.ui.escapeHtml(cover)}" alt="">`
        : '<span class="trash-row__empty">无图</span>';
      row.innerHTML = `
        <div class="trash-row__thumb">${thumb}</div>
        <div class="trash-row__info">
          <p class="trash-row__name">${App.ui.escapeHtml(item.name)}</p>
          <p class="trash-row__meta">${item.item_count} 件 · 删除于 ${App.ui.escapeHtml(item.deleted_at || '')}</p>
        </div>
        <div class="trash-row__actions">
          <button class="btn btn--ghost" type="button" data-action="restore">恢复</button>
          <button class="btn btn--ghost btn--danger" type="button" data-action="purge">彻底删除</button>
        </div>
      `;
      row.querySelector('[data-action="restore"]').addEventListener('click', () => {
        restore('outfits', item);
      });
      row.querySelector('[data-action="purge"]').addEventListener('click', () => {
        purge('outfits', item);
      });
      els.outfits.appendChild(row);
    });
  }

  async function restore(kind, item) {
    try {
      await App.api.post(`/api/trash/${kind}/${item.id}/restore`);
      App.ui.toast(kind === 'garments' ? '衣服已恢复' : '搭配已恢复');
      if (kind === 'garments') {
        App.wardrobe.load();
      } else {
        App.outfits.load();
      }
      load();
    } catch (err) {
      App.ui.toast(err.message, 'error');
    }
  }

  async function purge(kind, item) {
    const label = kind === 'garments' ? '衣服' : '搭配';
    const confirmed = await App.ui.confirm({
      title: `彻底删除这件${label}？`,
      message:
        kind === 'garments'
          ? '图片文件会被真正删除，并会从所有搭配中移除，无法恢复。'
          : '画布布局和已上传的上身图会被真正删除，无法恢复。',
      confirmText: '彻底删除',
    });
    if (!confirmed) return;

    try {
      await App.api.del(`/api/trash/${kind}/${item.id}`);
      App.ui.toast('已彻底删除');
      load();
    } catch (err) {
      App.ui.toast(err.message, 'error');
    }
  }

  // ---------------------------------------------------------------- 备份

  async function backup() {
    els.backupBtn.disabled = true;
    els.backupBtn.textContent = '备份中…';

    try {
      const result = await App.api.post('/api/backup');
      App.ui.toast(`已备份：${result.name}`);
      load();
    } catch (err) {
      App.ui.toast(err.message, 'error');
    } finally {
      els.backupBtn.disabled = false;
      els.backupBtn.textContent = '立即备份';
    }
  }

  // ---------------------------------------------------------------- 加载

  async function load() {
    try {
      const data = await App.api.get('/api/trash');
      state.data = data;
      renderGarments(data.garments || []);
      renderOutfits(data.outfits || []);

      const latest = (data.backups || [])[0];
      els.backupInfo.textContent = latest
        ? `最近备份：${latest.name}（${formatSize(latest.size)}，${latest.mtime}）`
        : '最近备份：还没有备份';
    } catch (err) {
      App.ui.toast(err.message, 'error');
    }
  }

  function init(_meta) {
    cache();
    els.backupBtn.addEventListener('click', backup);
    els.welcomeToggle.checked = App.welcome.isEnabled();
    els.welcomeToggle.addEventListener('change', () => {
      const on = els.welcomeToggle.checked;
      App.welcome.setEnabled(on);
      App.ui.toast(on ? '下次启动会显示欢迎页' : '已关闭启动欢迎页');
    });
    load();
  }

  App.settings = { init, load };
})(window.App = window.App || {});
