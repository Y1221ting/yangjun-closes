/* 后端请求封装：统一错误处理，失败时抛出带中文消息的 Error。 */
(function (App) {
  'use strict';

  async function request(method, url, body) {
    const options = { method, headers: {} };

    if (body instanceof Blob) {
      options.headers['Content-Type'] = body.type || 'application/octet-stream';
      options.body = body;
    } else if (body !== undefined) {
      options.headers['Content-Type'] = 'application/json';
      options.body = JSON.stringify(body);
    }

    let response;
    try {
      response = await fetch(url, options);
    } catch (err) {
      throw new Error('无法连接本地服务，请重启程序后再试');
    }

    let payload;
    try {
      payload = await response.json();
    } catch (err) {
      throw new Error('本地服务返回了无法解析的内容');
    }

    if (!response.ok || !payload.ok) {
      throw new Error(payload.error || `请求失败（${response.status}）`);
    }
    return payload.data;
  }

  App.api = {
    get: (url) => request('GET', url),
    post: (url, body) => request('POST', url, body),
    put: (url, body) => request('PUT', url, body),
    del: (url) => request('DELETE', url),
    upload: (url, blob) => request('POST', url, blob),
  };
})(window.App = window.App || {});
