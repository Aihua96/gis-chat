/** GIS 统计证据的展示：指标、图层明细、质检提示与示意图。 */
import { api } from '../core/api.js';
import { formatNumber, html } from '../core/dom.js';

const layerRows = layers => Object.entries(layers).map(([name, stat]) => html`
  <tr>
    <td>${name}</td>
    <td class="num">${stat.count}</td>
    <td class="num">${stat.area ? formatNumber(stat.area) : '—'}</td>
    <td class="num">${stat.length ? formatNumber(stat.length) : '—'}</td>
  </tr>`);

export const evidencePanel = (projectId, evidence) => {
  if (!evidence) return html`<div class="empty">导入矢量成果后，这里会显示统计与质检结果。</div>`;
  return html`
    <dl class="metrics">
      <div><dt>要素总数</dt><dd>${evidence.feature_count}</dd></div>
      <div><dt>面状面积（㎡）</dt><dd>${formatNumber(evidence.total_area)}</dd></div>
      <div><dt>线状长度（m）</dt><dd>${formatNumber(evidence.total_length)}</dd></div>
    </dl>

    ${evidence.warnings.length
      ? evidence.warnings.map(item => html`<div class="warn">需复核：${item}</div>`)
      : html`<p class="ok-text" style="margin-top:var(--s-3)">✓ 基础检查未发现异常</p>`}

    <details class="fold">
      <summary>图层明细与示意图</summary>
      <div>
        <div class="scroll-x">
          <table class="table">
            <thead><tr><th>图层</th><th>要素数</th><th>面积（㎡）</th><th>长度（m）</th></tr></thead>
            <tbody>${layerRows(evidence.layers)}</tbody>
          </table>
        </div>
        <img class="preview" alt="测区成果示意图" src="${api.previewUrl(projectId)}">
        <p class="hint">空间参考：${evidence.crs}　数值由 GIS 引擎确定性计算，不经过大模型。</p>
      </div>
    </details>`;
};
