"""报告叙述性章节的生成。

产品约束：数值（面积、长度、要素数、坐标系）全部来自 GIS 引擎的 Evidence，
模型只负责组织语言。未配置模型时退回受控模板，保证流程随时可跑通。
"""
import json

from ..domain import Evidence, LlmError, LlmSetting, Narrative, Project
from .client import OpenAICompatibleClient

SECTION_KEYS = ['项目概况', '技术路线', '质量评价', '结论与建议']
SYSTEM_PROMPT = '你只能基于给定证据编写测绘技术报告。'
MATERIAL_LIMIT = 12000

def build_prompt(project: Project, evidence: Evidence, description: str, material: str) -> str:
    context = json.dumps({'project': project.to_dict(), 'statistics': evidence.to_dict()}, ensure_ascii=False)
    return f'''你是测绘工程技术报告助手。根据项目描述、项目资料和 GIS 引擎证据，生成中文报告的分析性章节。严格规则：
1) 只能引用 GIS 证据中的数值；不得自行计算或杜撰面积、长度、精度、坐标、日期或规范条款。
2) 对缺失信息明确写“待人工补充/核验”，不要猜测。
3) 不要输出 Markdown、标题编号、免责声明或数据表；只返回 JSON 对象，键必须为：{"、".join(SECTION_KEYS)}。
4) 每个值为 80—220 字的正式中文段落。

用户描述：{description or '未提供'}
项目资料摘录：{material[:MATERIAL_LIMIT] or '未提供'}
GIS 引擎证据（可信数值来源）：{context}'''

def template_narrative(project: Project, evidence: Evidence, description: str, material: str) -> Narrative:
    """未配置模型时的受控模板，用词保守且不引入任何新数值。"""
    intro = description.strip() or project.description.strip() or '用户未补充项目描述，以下内容依据导入矢量成果生成。'
    material_note = '已参考上传项目资料。' if material.strip() else '未上传文本资料，建议补充任务书、设计书或作业记录。'
    if evidence.warnings:
        quality = f'系统检出 {len(evidence.warnings)} 项需人工复核事项：' + '；'.join(evidence.warnings) + '。'
    else:
        quality = '基础属性完整性与支持的几何类型检查未发现异常。'
    return Narrative(mode='template', source='演示模式（未配置大模型）', sections={
        '项目概况': f'{intro}。本项目处理 {evidence.feature_count} 个空间要素，空间参考为 {evidence.crs}。{material_note}',
        '技术路线': '外业成果经数据导入后，由 GIS 引擎完成几何类型识别、图层统计、面积长度计算及基础规则检查；'
                    '系统将确定性计算结果作为报告数据来源。',
        '质量评价': quality + ' 本评价为 AI 辅助初稿，最终结论须由项目负责人审核确认。',
        '结论与建议': '建议在归档前完成异常项复核，并核验项目资料、图件编号、精度指标及最终签章信息。',
    })

class NarrativeGenerator:
    """通过注入 client_factory 替换模型供应商，便于测试与内外网切换。"""

    def __init__(self, client_factory=OpenAICompatibleClient):
        self.client_factory = client_factory

    def generate(self, project: Project, evidence: Evidence, description: str,
                 material: str, setting: LlmSetting) -> Narrative:
        if not setting.configured:
            return template_narrative(project, evidence, description, material)
        payload = self.client_factory(setting).complete_json(
            SYSTEM_PROMPT, build_prompt(project, evidence, description, material))
        if not all(isinstance(payload.get(key), str) and payload[key].strip() for key in SECTION_KEYS):
            raise LlmError('模型未按约定返回完整章节，请更换模型或重试')
        return Narrative(sections={key: payload[key].strip() for key in SECTION_KEYS},
                         source='大模型生成：' + setting.model, mode='llm')
