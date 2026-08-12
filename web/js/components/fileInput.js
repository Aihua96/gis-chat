/** 文件选择：统一处理隐藏 input 的样式结构与 base64 读取。 */
import { html } from '../core/dom.js';

/** 渲染一个看起来像按钮的文件选择器。id 用于事件绑定。 */
export const fileButton = ({ id, label, accept, ghost = false }) => html`
  <span class="file-btn">
    <button type="button" class="btn ${ghost ? 'ghost' : ''}">${label}</button>
    <input type="file" id="${id}" accept="${accept}">
  </span>`;

export const readAsBase64 = file => new Promise((resolve, reject) => {
  const reader = new FileReader();
  reader.onload = () => resolve(reader.result.split(',')[1]);
  reader.onerror = () => reject(new Error('文件读取失败'));
  reader.readAsDataURL(file);
});

/** 绑定 change 事件，回调拿到 File；处理完自动清空，便于重复选同一个文件。 */
export function onFileSelected(input, handler) {
  if (!input) return;
  input.addEventListener('change', async event => {
    const file = event.target.files[0];
    if (!file) return;
    try {
      await handler(file);
    } finally {
      event.target.value = '';
    }
  });
}
