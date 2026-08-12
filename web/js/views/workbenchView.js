/** 项目工作台：上传资料 → 导入成果 → 描述需求 → 生成报告，一条线走完。 */
import { api } from '../core/api.js';
import { $, bind, formatTime, html, mount } from '../core/dom.js';
import { docxAvailable, getState, llmSettings, materialSuffixes, setState, templates } from '../core/store.js';
import { evidencePanel } from '../components/evidencePanel.js';
import { fileButton, onFileSelected, readAsBase64 } from '../components/fileInput.js';
import { run, toast } from '../components/toast.js';

const step = (no, title, state, body) => html`
  <section class="card">
    <div class="step-title">
      <span class="no">${no}</span>
      <h2>${title}</h2>
      ${state ? html`<span class="state">${state}</span>` : ''}
    </div>
    ${body}
  </section>`;

const materialList = materials => materials.length
  ? materials.map(item => html`
      <div class="list-row">
        <div>
          <strong>${item.filename}</strong>
          <div class="meta">${item.chars} 字符 · ${formatTime(item.uploaded_at)}</div>
        </div>
      </div>`)
  : html`<div class="empty">可上传任务书、设计书或作业记录，作为 AI 撰写的参考材料。不传也能生成。</div>`;

const reportList = reports => reports.length
  ? reports.map(report => html`
      <div class="list-row">
        <div>
          <strong>${report.template_name}</strong>
          <div class="meta">${formatTime(report.created_at)} · ${report.source}</div>
        </div>
        <a class="btn ghost sm" href="${report.url}" target="_blank" rel="noopener">下载</a>
      </div>`)
  : html`<div class="empty">还没有生成过报告。</div>`;

const template = ({ project, evidence, reports }) => {
  const settings = llmSettings();
  return html`
    <div class="page-head">
      <h1>${project.name}</h1>
      <p class="sub">
        <a href="#/">← 返回项目列表</a> ·
        <span class="chip ${project.status}">${project.status_label}</span> ·
        ${project.type || '未填写类型'}
      </p>
    </div>

    ${step(1, '项目资料', null, html`
      ${materialList(project.materials)}
      <div class="actions" style="margin-top:var(--s-3)">
        ${fileButton({ id: 'material', label: '上传资料', accept: materialSuffixes().join(','), ghost: true })}
        <span class="faint" style="font-size:var(--f-xs)">支持 ${materialSuffixes().join(' / ')}</span>
      </div>`)}

    ${step(2, '矢量成果', evidence ? html`<span class="chip imported">已导入</span>` : '', html`
      <div class="actions" style="margin-bottom:var(--s-3)">
        ${fileButton({ id: 'dataset', label: '导入 GeoJSON / SHP ZIP', accept: '.json,.geojson,.zip' })}
        <button class="btn ghost" id="demo-data">导入内置演示成果</button>
      </div>
      ${evidencePanel(project.id, evidence)}
      <p class="hint">SHP 请将同名 .shp、.dbf、.shx、.prj 一并压缩。面积与长度按投影平面坐标计算。</p>`)}

    ${step(3, '生成报告', null, html`
      <label class="field">
        <span>报告模板</span>
        <select id="template">
          ${templates().map(item => html`<option value="${item.id}">${item.name}</option>`)}
        </select>
      </label>
      <label class="field">
        <span>需求描述</span>
        <textarea id="description" rows="4"
          placeholder="例：编制本项目道路竣工测量技术总结，重点说明成果统计、质量情况和需复核事项。">${project.description}</textarea>
      </label>

      <details class="fold">
        <summary>大模型配置（可选）</summary>
        <div>
          <label class="field">
            <span>OpenAI 兼容 Base URL</span>
            <input id="base-url" value="${settings.base_url}" placeholder="http://模型服务器:8000/v1">
          </label>
          <div class="field-row">
            <label class="field">
              <span>模型名称</span>
              <input id="model" value="${settings.model}" placeholder="Qwen3-32B / deepseek-chat">
            </label>
            <label class="field">
              <span>API Key（仅本次请求使用，不落盘）</span>
              <input id="api-key" type="password" value="${getState().apiKey}" placeholder="本地服务可留空">
            </label>
          </div>
          <div class="actions"><button class="btn ghost sm" id="save-settings">保存地址与模型</button></div>
          <p class="hint">未配置时按受控模板生成，流程照常跑通。</p>
        </div>
      </details>

      <div class="actions" style="margin-top:var(--s-4)">
        <button class="btn" id="generate" ${evidence ? '' : 'disabled'}>生成 Word 报告</button>
        ${evidence ? '' : html`<span class="faint" style="font-size:var(--f-xs)">请先导入矢量成果</span>`}
        ${docxAvailable() ? '' : html`<span class="error-text" style="font-size:var(--f-xs)">未安装 python-docx，导出不可用</span>`}
      </div>`)}

    <section class="card">
      <h2>已生成的报告</h2>
      ${reportList(reports)}
    </section>`;
};

export async function workbenchView(container, projectId) {
  const detail = await api.getProject(projectId);
  mount(container, template(detail));

  const refresh = () => workbenchView(container, projectId);

  onFileSelected($('#material', container), file => run(async () => {
    await api.addMaterial(projectId, file.name, await readAsBase64(file));
    toast(`已提取 ${file.name}`);
    await refresh();
  }));

  onFileSelected($('#dataset', container), file => run(async () => {
    const source = file.name.toLowerCase().endsWith('.zip')
      ? { format: 'shpzip', content: await readAsBase64(file) }
      : JSON.parse(await file.text());
    await api.importDataset(projectId, source, file.name);
    toast('矢量成果已导入');
    await refresh();
  }));

  bind(container, '#demo-data', 'click', () => run(async () => {
    await api.importDataset(projectId, await api.demoGeojson(), '内置演示数据 demo_project.geojson');
    toast('演示成果已导入');
    await refresh();
  }));

  bind(container, '#save-settings', 'click', () => run(async () => {
    const saved = await api.saveSettings({
      base_url: $('#base-url', container).value.trim(),
      model: $('#model', container).value.trim(),
    });
    setState({ meta: { ...getState().meta, settings: saved } });
    toast('模型配置已保存');
  }));

  bind(container, '#generate', 'click', event => {
    const button = event.currentTarget;
    setState({ apiKey: $('#api-key', container).value });
    button.disabled = true;
    button.textContent = '生成中…（模型较慢时最长约 90 秒）';
    run(async () => {
      const report = await api.createReport(projectId, {
        template: $('#template', container).value,
        description: $('#description', container).value,
        llm: {
          base_url: $('#base-url', container).value.trim(),
          model: $('#model', container).value.trim(),
          api_key: getState().apiKey,
        },
      });
      toast(`报告已生成（${report.mode === 'llm' ? '大模型模式' : '受控模板模式'}）`);
      window.open(report.url, '_blank');
    }).finally(refresh);
  });
}
