"""报告叙述性章节的生成：优先调用 OpenAI 兼容接口，未配置模型时回退到受控模板。

数值（面积、长度、要素数、坐标系）一律来自 gis_service 的确定性计算，
本模块只负责把这些证据交给模型组织语言，提示词中明确禁止模型自行推算数值。
"""
import json, re
from urllib.request import Request, urlopen

from .config import PROJECT

SECTION_KEYS = ['项目概况', '技术路线', '质量评价', '结论与建议']

def _fallback_sections(evidence, description, material):
    project_note = description.strip() or '用户未补充项目描述，以下内容依据导入矢量成果生成。'
    material_note = '已参考上传项目资料。' if material.strip() else '未上传文本资料，建议补充任务书、设计书或作业记录。'
    warnings = evidence['warnings']
    quality = ('系统检出 '+str(len(warnings))+' 项需人工复核事项：'+'；'.join(warnings)+'。') if warnings else '基础属性完整性与支持的几何类型检查未发现异常。'
    return {
        '项目概况': f'{project_note}。本项目处理 {evidence["feature_count"]} 个空间要素，空间参考为 {evidence["crs"]}。{material_note}',
        '技术路线': '外业成果经数据导入后，由 GIS 引擎完成几何类型识别、图层统计、面积长度计算及基础规则检查；系统将确定性计算结果作为报告数据来源。',
        '质量评价': quality+' 本评价为 AI 辅助初稿，最终结论须由项目负责人审核确认。',
        '结论与建议': '建议在归档前完成异常项复核，并核验项目资料、图件编号、精度指标及最终签章信息。',
    }

def _endpoint(base_url):
    base = base_url.rstrip('/')
    if base.endswith('/chat/completions'): return base
    return base + ('/chat/completions' if base.endswith('/v1') else '/v1/chat/completions')

def _prompt(evidence, description, material):
    context = json.dumps({'statistics': evidence, 'project': PROJECT}, ensure_ascii=False)
    return f'''你是测绘工程技术报告助手。根据项目描述、项目资料和 GIS 引擎证据，生成中文报告的分析性章节。严格规则：
1) 只能引用 GIS 证据中的数值；不得自行计算或杜撰面积、长度、精度、坐标、日期或规范条款。
2) 对缺失信息明确写“待人工补充/核验”，不要猜测。
3) 不要输出 Markdown、标题编号、免责声明或数据表；只返回 JSON 对象，键必须为：{"、".join(SECTION_KEYS)}。
4) 每个值为 80—220 字的正式中文段落。

用户描述：{description or '未提供'}
项目资料摘录：{material[:12000] or '未提供'}
GIS 引擎证据（可信数值来源）：{context}'''

def compose_sections(evidence, description, material, config):
    """返回 (章节字典, 生成方式说明)。未配置 Base URL 或模型名时走演示模板。"""
    if not config or not config.get('base_url') or not config.get('model'):
        return _fallback_sections(evidence, description, material), '演示模式（未配置大模型）'
    headers = {'Content-Type': 'application/json'}
    if config.get('api_key'): headers['Authorization'] = 'Bearer '+config['api_key']
    body = json.dumps({'model': config['model'], 'temperature': 0.2, 'response_format': {'type': 'json_object'},
                       'messages': [{'role': 'system', 'content': '你只能基于给定证据编写测绘技术报告。'},
                                    {'role': 'user', 'content': _prompt(evidence, description, material)}]}).encode()
    try:
        request = Request(_endpoint(config['base_url']), data=body, headers=headers, method='POST')
        with urlopen(request, timeout=90) as response:
            content = json.loads(response.read().decode())['choices'][0]['message']['content']
        sections = json.loads(re.sub(r'^```json\s*|\s*```$', '', content.strip()))
        if not all(isinstance(sections.get(key), str) for key in SECTION_KEYS):
            raise ValueError('模型未按约定返回完整章节')
        return {key: sections[key].strip() for key in SECTION_KEYS}, '大模型生成：'+config['model']
    except Exception as exc:
        raise RuntimeError('大模型调用失败：'+str(exc)) from exc
