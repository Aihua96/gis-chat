/** 极简哈希路由：注册 正则 → 视图函数，视图自行渲染到容器。 */

const routes = [];
let container = null;
let fallback = null;

export const route = (pattern, view) => routes.push({ pattern, view });
export const setFallback = view => { fallback = view; };
export const go = path => { window.location.hash = path; };

async function resolve() {
  const path = window.location.hash.slice(1) || '/';
  for (const { pattern, view } of routes) {
    const match = path.match(pattern);
    if (match) return view(container, ...match.slice(1));
  }
  if (fallback) fallback(container);
}

export function start(target) {
  container = target;
  window.addEventListener('hashchange', resolve);
  return resolve();
}

export const reload = resolve;
