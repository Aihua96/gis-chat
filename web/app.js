/* 前端：项目列表 + 项目工作台。按 视图渲染 / 接口访问 / 交互动作 三段组织。 */

// ---------- 基础工具 ----------

const esc = value => String(value ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const num = value => Number(value || 0).toLocaleString('zh-CN', { maximumFractionDigits: 2 });
const el = id => document.getElementById(id);
const value = id => (el(id) ? el(id).value.trim() : '');

let toastTimer;
function toast(message, bad = false) {
  const box = el('toast');
  box.textContent = message;
  box.className = 'toast' + (bad ? ' bad' : '');
  box.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { box.hidden = true; }, 4000);
}

async function request(url, options = {}) {
  const response = await fetch(url, options);
  const data = response.status === 204 ? {} : await response.json();
  if (!response.ok) throw new Error(data.error || '操作失败');
  return data;
}
const api = {
  get: url => request(url),
  post: (url, body) => request(url, { method: 'POST', body: JSON.stringify(body || {}) }),
  put: (url, body) => request(url, { method: 'PUT', body: JSON.stringify(body || {}) }),
  del: url => request(url, { method: 'DELETE' }),
};

function readFileAsBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result.split(',')[1]);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

// ---------- 应用状态 ----------

const state = { meta: null, projects: [], detail: null, apiKey: '', busy: false };

// ---------- 视图：项目列表 ----------

function projectListView() {
  const rows = state.projects.map(project => `
    <div class="list-row">
      <div>
        <strong><a href="#/projects/${esc(project.id)}">${esc(project.name)}</a></strong>
        <div class="meta">${esc(project.type || '未填写类型')} · 创建于 ${esc(project.created_at.replace('T', ' '))}</div>
      </div>
      <div class="actions" style="margin:0">
        <span class="badge ${esc(project.status)}">${esc(project.status_label)}</span>
        <button class="danger" data-delete="${esc(project.id)}">删除</button>
      </div>
    </div>`).join('');

  return `
    <div class="page-head">
      <div><h1>项目</h1><p class="muted">每个项目独立保存资料、矢量成果与报告历史。</p></div>
      <button class="secondary" id="demoBtn">创建示例项目并导入成果</button>
    </div>
    <div class="grid">
      <div class="card">
        <h2>项目列表</h2>
        ${rows || '<div class="empty">还没有项目。右侧新建一个，或用示例项目快速跑通流程。</div>'}
      </div>
      <div class="card">
        <h2>新建项目</h2>
        <label class="label">项目名称（必填）</label>
        <input class="field" id="name" placeholder="例：新城产业园西侧配套道路竣工测量项目">
        <div class="two">
          <div><label class="label">项目类型</label><input class="field" id="type" placeholder="工程测量（道路竣工测量）"></div>
          <div><label class="label">测区位置</label><input class="field" id="location" placeholder="四川省成都市…"></div>
          <div><label class="label">作业周期</label><input class="field" id="period" placeholder="2026年7月15日—7月22日"></div>
          <div><label class="label">承担单位</label><input class="field" id="unit" placeholder="××测绘院"></div>
        </div>
        <label class="label">坐标系统（留空则取自导入成果）</label>
        <input class="field" id="coordinate_system" placeholder="${esc(state.meta?.settings ? 'CGCS2000 / 3度分带高斯-克吕格投影' : '')}">
        <label class="label">主要仪器</label>
        <input class="field" id="instrument" placeholder="GNSS 接收机、全站仪…">
        <div class="actions"><button id="createBtn">创建项目</button></div>
      </div>
    </div>`;
}

// ---------- 视图：项目工作台 ----------

function stepsBar(project) {
  const done = { draft: 1, imported: 2, reported: 4 }[project.status] || 1;
  const labels = [['01 项目创建', '基本信息'], ['02 成果导入', '资料与矢量数据'],
                  ['03 统计质检', '可验证空间证据'], ['04 报告导出', 'AI 初稿']];
  return `<nav class="steps">${labels.map(([title, sub], index) =>
    `<div class="step ${index < done ? 'done' : ''}"><b>${title}</b>${sub}</div>`).join('')}</nav>`;
}

function evidenceCard(project, evidence) {
  if (!evidence) return `<div class="card"><h2>统计与质检</h2><div class="empty">导入矢量成果后自动生成统计、质检与示意图。</div></div>`;
  const layers = Object.entries(evidence.layers).map(([name, stat]) => `
    <tr><td>${esc(name)}</td><td>${stat.count}</td>
      <td>${stat.area ? num(stat.area) : '—'}</td><td>${stat.length ? num(stat.length) : '—'}</td></tr>`).join('');
  const warnings = evidence.warnings.length
    ? evidence.warnings.map(item => `<div class="warn">需复核：${esc(item)}</div>`).join('')
    : '<p class="ok">✓ 基础检查未发现异常</p>';
  return `
    <div class="card">
      <h2>统计与质检</h2>
      <div class="metric">
        <div><span>要素总数</span><strong>${evidence.feature_count}</strong></div>
        <div><span>面状面积</span><strong>${num(evidence.total_area)} ㎡</strong></div>
        <div><span>线状长度</span><strong>${num(evidence.total_length)} m</strong></div>
      </div>
      <h3>图层统计（报告引用口径）</h3>
      <table><thead><tr><th>图层</th><th>要素数</th><th>面积（㎡）</th><th>长度（m）</th></tr></thead><tbody>${layers}</tbody></table>
      <h3>质检结果</h3>
      ${warnings}
      <h3>测区成果示意图</h3>
      <img class="preview" alt="测区成果示意图" src="/api/projects/${esc(project.id)}/preview.svg?t=${Date.now()}">
      <div class="trace">来源：${esc(project.dataset?.source || '未记录')}
空间参考：${esc(evidence.crs)}
计算：面积 / 长度 / 要素计数 / 基础检查（确定性程序，不经过大模型）</div>
    </div>`;
}

function reportsCard(reports) {
  const rows = reports.map(report => `
    <div class="list-row">
      <div>
        <strong>${esc(report.template_name)}</strong>
        <div class="meta">${esc(report.created_at.replace('T', ' '))} · ${esc(report.source)}</div>
      </div>
      <a class="badge" href="${esc(report.url)}" target="_blank" rel="noopener">下载</a>
    </div>`).join('');
  return `<div class="card"><h2>报告历史</h2>${rows || '<div class="empty">尚未生成报告。</div>'}</div>`;
}

function projectView() {
  const { project, evidence, reports } = state.detail;
  const settings = state.meta?.settings || {};
  const templates = (state.meta?.templates || []).map(item =>
    `<option value="${esc(item.id)}">${esc(item.name)}</option>`).join('');
  const materials = project.materials.length
    ? project.materials.map(item => `<div class="list-row"><div><strong>${esc(item.filename)}</strong>
        <div class="meta">${item.chars} 字符 · ${esc(item.uploaded_at.replace('T', ' '))}</div></div></div>`).join('')
    : '<div class="empty">未上传资料。可补充任务书、设计书或作业记录，供 AI 参考。</div>';
  const info = [['项目类型', project.type], ['测区位置', project.location], ['作业周期', project.period],
                ['承担单位', project.unit], ['主要仪器', project.instrument], ['坐标系统', project.coordinate_system]];

  return `
    <div class="page-head">
      <div>
        <h1>${esc(project.name)}</h1>
        <p class="muted"><a href="#/">← 返回项目列表</a> · <span class="badge ${esc(project.status)}">${esc(project.status_label)}</span></p>
      </div>
    </div>
    ${stepsBar(project)}
    <div class="grid">
      <div>
        <div class="card">
          <h2>项目信息</h2>
          <table><tbody>${info.map(([key, val]) =>
            `<tr><th style="width:110px">${key}</th><td>${esc(val || '待补充')}</td></tr>`).join('')}</tbody></table>
        </div>
        <div class="card">
          <h2>项目资料</h2>
          ${materials}
          <div class="actions">
            <label class="file">上传资料（${esc((state.meta?.material_suffixes || []).join(' / '))}）
              <input type="file" id="materialInput" accept="${esc((state.meta?.material_suffixes || []).join(','))}">
            </label>
          </div>
        </div>
        <div class="card">
          <h2>矢量成果</h2>
          <p class="note" style="margin-top:0">SHP 请将同名 .shp、.dbf、.shx、.prj 一并压缩。面积与长度按投影平面坐标计算。</p>
          <div class="actions">
            <label class="file">导入 GeoJSON / SHP ZIP<input type="file" id="datasetInput" accept=".json,.geojson,.zip"></label>
            <button class="secondary" id="demoDataBtn">导入内置演示成果</button>
            <button class="secondary" onclick="location='/api/demo.geojson'">下载示例 GeoJSON</button>
            <button class="secondary" onclick="location='/api/demo-shp.zip'">下载示例 SHP ZIP</button>
          </div>
        </div>
        ${evidenceCard(project, evidence)}
      </div>
      <div>
        <div class="card">
          <h2>大模型配置</h2>
          <label class="label">OpenAI 兼容 Base URL</label>
          <input class="field" id="baseUrl" value="${esc(settings.base_url || '')}" placeholder="http://模型服务器:8000/v1">
          <label class="label">模型名称</label>
          <input class="field" id="model" value="${esc(settings.model || '')}" placeholder="Qwen3-32B / deepseek-chat">
          <label class="label">API Key（仅本次请求使用，不落盘）</label>
          <input class="field" id="apiKey" type="password" value="${esc(state.apiKey)}" placeholder="本地服务可留空">
          <div class="actions"><button class="secondary" id="saveSettingsBtn">保存地址与模型</button></div>
          <p class="note">未配置时按受控模板生成，流程照常跑通。配置后由模型撰写项目概况、技术路线、质量评价与结论建议。</p>
        </div>
        <div class="card">
          <h2>生成报告</h2>
          <label class="label">报告模板</label>
          <select class="field" id="template">${templates}</select>
          <label class="label">用户需求描述</label>
          <textarea class="field" id="description" rows="4">${esc(project.description)}</textarea>
          <div class="actions">
            <button id="reportBtn" ${evidence ? '' : 'disabled'}>${state.busy ? '生成中…' : '生成 Word 报告'}</button>
          </div>
          <p class="note">${evidence ? '数值来自 GIS 引擎，模型只负责成文。' : '请先导入矢量成果。'}
            ${state.meta?.docx_available ? '' : '<span class="error">未安装 python-docx，报告导出不可用。</span>'}</p>
        </div>
        ${reportsCard(reports)}
      </div>
    </div>`;
}

// ---------- 交互动作 ----------

async function guard(work) {
  try { await work(); } catch (error) { toast(error.message, true); }
}

function bindListView() {
  el('createBtn').onclick = () => guard(async () => {
    const payload = {};
    for (const key of ['name', 'type', 'location', 'period', 'unit', 'coordinate_system', 'instrument']) payload[key] = value(key);
    const { project } = await api.post('/api/projects', payload);
    toast('项目已创建');
    location.hash = `#/projects/${project.id}`;
  });
  el('demoBtn').onclick = () => guard(async () => {
    const { project } = await api.post('/api/projects/demo');
    toast('示例项目已创建，矢量成果已导入');
    location.hash = `#/projects/${project.id}`;
  });
  document.querySelectorAll('[data-delete]').forEach(button => {
    button.onclick = () => guard(async () => {
      if (!confirm('删除后该项目的成果与报告记录将一并移除，确认删除？')) return;
      await api.del('/api/projects/' + button.dataset.delete);
      toast('项目已删除');
      await render();
    });
  });
}

function bindProjectView(projectId) {
  el('materialInput').onchange = event => guard(async () => {
    const file = event.target.files[0];
    if (!file) return;
    await api.post(`/api/projects/${projectId}/materials`, { filename: file.name, content: await readFileAsBase64(file) });
    toast(`已提取 ${file.name}`);
    await render();
  });

  el('datasetInput').onchange = event => guard(async () => {
    const file = event.target.files[0];
    if (!file) return;
    const source = file.name.toLowerCase().endsWith('.zip')
      ? { format: 'shpzip', content: await readFileAsBase64(file) }
      : JSON.parse(await file.text());
    await api.post(`/api/projects/${projectId}/dataset`, { source, label: file.name });
    toast('矢量成果已导入');
    await render();
  });

  el('demoDataBtn').onclick = () => guard(async () => {
    const source = await api.get('/api/demo.geojson');
    await api.post(`/api/projects/${projectId}/dataset`, { source, label: '内置演示数据 demo_project.geojson' });
    toast('演示成果已导入');
    await render();
  });

  el('saveSettingsBtn').onclick = () => guard(async () => {
    state.meta.settings = await api.put('/api/settings', { base_url: value('baseUrl'), model: value('model') });
    toast('模型配置已保存');
  });

  el('reportBtn').onclick = () => guard(async () => {
    state.apiKey = el('apiKey').value;
    state.busy = true;
    el('reportBtn').disabled = true;
    el('reportBtn').textContent = '生成中…';
    try {
      const { report } = await api.post(`/api/projects/${projectId}/reports`, {
        template: value('template'),
        description: el('description').value,
        llm: { base_url: value('baseUrl'), model: value('model'), api_key: state.apiKey },
      });
      toast(`报告已生成（${report.mode === 'llm' ? '大模型模式' : '受控模板模式'}）`);
      window.open(report.url, '_blank');
    } finally {
      state.busy = false;
      await render();
    }
  });
}

// ---------- 路由 ----------

async function render() {
  const view = el('view');
  const match = location.hash.match(/^#\/projects\/([\w-]+)/);
  try {
    if (!state.meta) state.meta = await api.get('/api/meta');
    if (match) {
      state.detail = await api.get('/api/projects/' + match[1]);
      view.innerHTML = projectView();
      bindProjectView(match[1]);
    } else {
      state.projects = (await api.get('/api/projects')).projects;
      view.innerHTML = projectListView();
      bindListView();
    }
  } catch (error) {
    view.innerHTML = `<div class="card"><h2>出错了</h2><p class="error">${esc(error.message)}</p>
      <div class="actions"><a class="badge" href="#/">返回项目列表</a></div></div>`;
  }
}

window.addEventListener('hashchange', render);
render();
