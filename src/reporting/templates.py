"""报告模板注册表：新增模板只需在这里登记，前端选项由 /api/meta 下发。"""
from dataclasses import asdict, dataclass

from ..domain import ValidationError

@dataclass(frozen=True)
class ReportTemplate:
    id: str
    name: str
    title: str
    description: str

    def to_dict(self):
        return asdict(self)

TEMPLATES = {
    template.id: template for template in [
        ReportTemplate('engineering_summary', '工程测量技术总结报告', '工程测量技术总结报告',
                       '面向竣工/阶段成果归档，侧重成果统计与质量评价。'),
        ReportTemplate('engineering_design', '工程测量技术设计书', '工程测量技术设计书',
                       '面向作业前技术方案，侧重技术路线与作业要求。'),
    ]
}

DEFAULT_TEMPLATE = 'engineering_summary'

def list_templates():
    return [template.to_dict() for template in TEMPLATES.values()]

def get_template(template_id: str) -> ReportTemplate:
    template = TEMPLATES.get(template_id or DEFAULT_TEMPLATE)
    if not template:
        raise ValidationError(f'未知的报告模板：{template_id}')
    return template
