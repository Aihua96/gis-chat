/** 后端接口封装：视图层只调用这里的方法，不出现裸 URL。 */

async function request(url, method = 'GET', body) {
  const options = { method };
  if (body !== undefined) options.body = JSON.stringify(body);
  const response = await fetch(url, options);
  const data = response.status === 204 ? {} : await response.json();
  if (!response.ok) throw new Error(data.error || '操作失败');
  return data;
}

const project = id => `/api/projects/${encodeURIComponent(id)}`;

export const api = {
  meta: () => request('/api/meta'),
  saveSettings: setting => request('/api/settings', 'PUT', setting),

  listProjects: () => request('/api/projects').then(data => data.projects),
  createProject: payload => request('/api/projects', 'POST', payload).then(data => data.project),
  createDemoProject: () => request('/api/projects/demo', 'POST', {}).then(data => data.project),
  getProject: id => request(project(id)),
  deleteProject: id => request(project(id), 'DELETE'),

  importDataset: (id, source, label) => request(`${project(id)}/dataset`, 'POST', { source, label }),
  addMaterial: (id, filename, content) => request(`${project(id)}/materials`, 'POST', { filename, content }),
  createReport: (id, payload) => request(`${project(id)}/reports`, 'POST', payload).then(data => data.report),

  demoGeojson: () => request('/api/demo.geojson'),
  previewUrl: id => `${project(id)}/preview.svg?t=${Date.now()}`,
};
