/** DOM 与模板工具：html 标签模板默认转义插值，杜绝手写 esc 的遗漏。 */

const ENTITIES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };

export const escapeText = value => String(value ?? '').replace(/[&<>"']/g, ch => ENTITIES[ch]);

/** 已转义的片段。html`` 的结果即为 Raw，因此模板可以安全嵌套。 */
class Raw {
  constructor(value) { this.value = value; }
  toString() { return this.value; }
}

/** 显式声明一段内容无需转义（仅用于自己生成的可信标记，如服务端返回的 SVG）。 */
export const raw = value => new Raw(String(value ?? ''));

const interpolate = value => {
  if (value == null || value === false) return '';
  if (value instanceof Raw) return value.value;
  if (Array.isArray(value)) return value.map(interpolate).join('');
  return escapeText(value);
};

/** 用法：html`<p>${用户输入}</p>`，插值自动转义；嵌套 html`` 与数组自动展开。 */
export function html(strings, ...values) {
  let out = strings[0];
  for (let i = 0; i < values.length; i++) out += interpolate(values[i]) + strings[i + 1];
  return new Raw(out);
}

export const mount = (node, content) => { node.innerHTML = String(content); return node; };

export const $ = (selector, root = document) => root.querySelector(selector);
export const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

/** 绑定事件并自动捕获异常，避免每个 handler 都写一遍 try/catch。 */
export const bind = (root, selector, event, handler) => {
  const node = $(selector, root);
  if (node) node.addEventListener(event, handler);
  return node;
};

export const formatNumber = value =>
  Number(value || 0).toLocaleString('zh-CN', { maximumFractionDigits: 2 });

export const formatTime = value => String(value || '').replace('T', ' ');
