/** 应用入口：加载元信息、注册路由、启动。 */
import { api } from './core/api.js';
import { $, html, mount } from './core/dom.js';
import { route, setFallback, start } from './core/router.js';
import { setState } from './core/store.js';
import { projectsView } from './views/projectsView.js';
import { workbenchView } from './views/workbenchView.js';

const errorCard = message => html`
  <div class="card">
    <h2>出错了</h2>
    <p class="error-text">${message}</p>
    <div class="actions" style="margin-top:var(--s-3)">
      <a class="btn ghost" href="#/">返回项目列表</a>
    </div>
  </div>`;

/** 错误边界：视图抛错时展示提示，而不是留下一个空白页面。 */
const guarded = view => async (container, ...params) => {
  try {
    await view(container, ...params);
  } catch (error) {
    mount(container, errorCard(error.message));
  }
};

route(/^\/projects\/([\w-]+)$/, guarded(workbenchView));
route(/^\/$/, guarded(projectsView));
setFallback(guarded(projectsView));

async function boot() {
  const container = $('#view');
  try {
    setState({ meta: await api.meta() });
  } catch (error) {
    return mount(container, errorCard(`无法连接后端服务：${error.message}`));
  }
  await start(container);
}

boot();
