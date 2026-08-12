/** 全局提示条。成功用默认样式，失败用 error。 */

let node = null;
let timer = null;

export function toast(message, kind = 'info') {
  if (!node) {
    node = document.createElement('div');
    document.body.appendChild(node);
  }
  node.className = kind === 'error' ? 'toast error' : 'toast';
  node.textContent = message;
  node.hidden = false;
  clearTimeout(timer);
  timer = setTimeout(() => { node.hidden = true; }, 4000);
}

/** 统一的动作包装：捕获异常并提示，避免每个 handler 重复 try/catch。 */
export async function run(work, { onError } = {}) {
  try {
    await work();
  } catch (error) {
    toast(error.message, 'error');
    onError?.(error);
  }
}
