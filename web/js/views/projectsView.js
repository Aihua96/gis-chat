/** 项目列表视图：选择已有项目，或新建一个。 */
import { api } from '../core/api.js';
import { $, bind, formatTime, html, mount } from '../core/dom.js';
import { go, reload } from '../core/router.js';
import { run, toast } from '../components/toast.js';

// [字段名, 标签, 占位提示, 是否占满整行]
const FIELDS = [
  ['name', '项目名称（必填）', '例：新城产业园西侧配套道路竣工测量项目', true],
  ['type', '项目类型', '工程测量（道路竣工测量）'],
  ['location', '测区位置', '四川省成都市…'],
  ['period', '作业周期', '2026年7月15日—7月22日'],
  ['unit', '承担单位', '××测绘院'],
  ['coordinate_system', '坐标系统（留空则取自导入成果）', 'CGCS2000 / 3度分带高斯-克吕格投影', true],
];

const projectRow = project => html`
  <div class="list-row">
    <div>
      <a href="#/projects/${project.id}"><strong>${project.name}</strong></a>
      <div class="meta">${project.type || '未填写类型'} · 创建于 ${formatTime(project.created_at)}</div>
    </div>
    <div class="actions">
      <span class="chip ${project.status}">${project.status_label}</span>
      <button class="btn danger" data-delete="${project.id}">删除</button>
    </div>
  </div>`;

const template = projects => html`
  <div class="page-head">
    <h1>项目</h1>
    <p class="sub">每个项目独立保存资料、矢量成果与生成过的报告。</p>
  </div>

  <div class="card">
    <h2>项目列表</h2>
    ${projects.length
      ? projects.map(projectRow)
      : html`<div class="empty">还没有项目。可以新建一个，或直接创建示例项目跑通流程。</div>`}
    <div class="actions" style="margin-top:var(--s-3)">
      <button class="btn ghost" id="demo">创建示例项目并导入成果</button>
    </div>
  </div>

  <div class="card">
    <h2>新建项目</h2>
    <div class="field-row">
      ${FIELDS.map(([id, label, placeholder, wide]) => html`
        <label class="field ${wide ? 'wide' : ''}">
          <span>${label}</span>
          <input id="f-${id}" placeholder="${placeholder}">
        </label>`)}
    </div>
    <div class="actions"><button class="btn" id="create">创建项目</button></div>
  </div>`;

export async function projectsView(container) {
  const projects = await api.listProjects();
  mount(container, template(projects));

  bind(container, '#create', 'click', () => run(async () => {
    const payload = Object.fromEntries(FIELDS.map(([id]) => [id, $(`#f-${id}`, container).value.trim()]));
    const project = await api.createProject(payload);
    toast('项目已创建');
    go(`/projects/${project.id}`);
  }));

  bind(container, '#demo', 'click', () => run(async () => {
    const project = await api.createDemoProject();
    toast('示例项目已创建，矢量成果已导入');
    go(`/projects/${project.id}`);
  }));

  container.querySelectorAll('[data-delete]').forEach(button => {
    button.addEventListener('click', () => run(async () => {
      if (!confirm('删除后该项目的成果与报告记录将一并移除，确认删除？')) return;
      await api.deleteProject(button.dataset.delete);
      toast('项目已删除');
      await reload();
    }));
  });
}
