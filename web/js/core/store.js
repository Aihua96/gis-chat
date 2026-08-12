/** 跨视图共享的少量状态。刻意不做发布订阅：视图在操作后显式重新渲染。 */

const state = {
  meta: null,      // /api/meta 的结果：模板列表、支持格式、已保存的模型配置
  apiKey: '',      // 仅存在于内存，不写入服务端也不写入 localStorage
};

export const getState = () => state;
export const setState = patch => Object.assign(state, patch);

export const templates = () => state.meta?.templates || [];
export const materialSuffixes = () => state.meta?.material_suffixes || [];
export const llmSettings = () => state.meta?.settings || { base_url: '', model: '' };
export const docxAvailable = () => state.meta?.docx_available !== false;
