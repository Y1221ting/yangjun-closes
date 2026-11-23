/* 通用界面工具：轻提示、HTML 转义。 */
(function (App) {
  'use strict';

  const stack = document.getElementById('toast-stack');

  function toast(message, type) {
    const el = document.createElement('div');
    el.className = 'toast' + (type ? ` toast--${type}` : '');
    el.textContent = message;
    stack.appendChild(el);

    setTimeout(() => {
      el.classList.add('is-leaving');
      setTimeout(() => el.remove(), 220);
    }, 2600);
  }

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function confirm(options) {
    const settings = {
      title: '确认操作',
      message: '',
      confirmText: '删除',
      cancelText: '取消',
      danger: true,
      ...(options || {}),
    };

    return new Promise((resolve) => {
      if (document.querySelector('.modal')) {
        resolve(false);
        return;
      }

      const modal = document.createElement('div');
      modal.className = 'modal';
      modal.innerHTML = `
        <div class="modal__backdrop" data-action="cancel"></div>
        <div class="modal__panel" role="dialog" aria-modal="true">
          <h3 class="modal__title"></h3>
          <p class="modal__message"></p>
          <div class="modal__actions">
            <button type="button" class="btn btn--ghost" data-action="cancel"></button>
            <button type="button" class="btn ${settings.danger ? 'btn--danger-solid' : 'btn--primary'}" data-action="confirm"></button>
          </div>
        </div>
      `;

      modal.querySelector('.modal__title').textContent = settings.title;
      modal.querySelector('.modal__message').textContent = settings.message;

      const cancelButton = modal.querySelector('.modal__actions [data-action="cancel"]');
      const confirmButton = modal.querySelector('[data-action="confirm"]');
      cancelButton.textContent = settings.cancelText;
      confirmButton.textContent = settings.confirmText;

      let settled = false;

      function finish(result) {
        if (settled) return;
        settled = true;
        document.removeEventListener('keydown', onKey);
        modal.remove();
        resolve(result);
      }

      function onKey(event) {
        if (event.key === 'Escape') {
          event.preventDefault();
          finish(false);
        }
      }

      modal.addEventListener('click', (event) => {
        const target = event.target.closest('[data-action]');
        if (!target) return;
        finish(target.dataset.action === 'confirm');
      });

      document.addEventListener('keydown', onKey);
      document.body.appendChild(modal);
      cancelButton.focus();
    });
  }

  App.ui = { toast, escapeHtml, confirm };
})(window.App = window.App || {});
