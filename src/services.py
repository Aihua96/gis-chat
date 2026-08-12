"""应用服务层：编排一个个完整用例，是 HTTP 层唯一可以调用的入口。

依赖（仓储、模型生成器、输出目录）全部由构造函数注入，因此服务层不依赖
具体的存储实现或模型供应商，替换实现不需要改这里的代码。
"""
import json, re
from pathlib import Path
from uuid import uuid4

from . import gis
from .ai import NarrativeGenerator
from .domain import (DatasetInfo, Evidence, IMPORTED, LlmSetting, MaterialInfo, NotFoundError,
                     Project, REPORTED, Report, ValidationError)
from .reporting import extract_text, get_template, render

UNSAFE_NAME = re.compile(r'[^\w-]+')  # \w 在 Unicode 模式下已包含中文

def _safe_filename(name: str) -> str:
    cleaned = UNSAFE_NAME.sub('_', name or '').strip('_.')
    return cleaned[:30] or 'report'

class ProjectService:
    """项目的创建、查询与聚合视图。"""

    def __init__(self, projects, data_store, reports, datasets: 'DatasetService',
                 demo_seed: dict, demo_dataset_path: Path):
        self.projects = projects
        self.data_store = data_store
        self.reports = reports
        self.datasets = datasets
        self.demo_seed = demo_seed
        self.demo_dataset_path = demo_dataset_path

    def create(self, payload: dict) -> Project:
        payload = payload or {}
        name = str(payload.get('name') or '').strip()
        if not name:
            raise ValidationError('项目名称不能为空')
        project = Project(
            name=name,
            type=str(payload.get('type') or '').strip(),
            location=str(payload.get('location') or '').strip(),
            coordinate_system=str(payload.get('coordinate_system') or '').strip(),
            period=str(payload.get('period') or '').strip(),
            unit=str(payload.get('unit') or '').strip(),
            instrument=str(payload.get('instrument') or '').strip(),
            description=str(payload.get('description') or '').strip(),
        )
        return self.projects.save(project)

    def create_demo(self) -> Project:
        """一键创建示例项目并导入内置成果，用于快速跑通完整流程。"""
        project = self.create(dict(self.demo_seed))
        data = json.loads(self.demo_dataset_path.read_text(encoding='utf-8'))
        self.datasets.import_vector(project.id, data, '内置演示数据 demo_project.geojson')
        return self.get(project.id)

    def list(self) -> list[Project]:
        return self.projects.list()

    def get(self, project_id: str) -> Project:
        project = self.projects.get(project_id)
        if not project:
            raise NotFoundError('项目不存在或已被删除')
        return project

    def detail(self, project_id: str) -> dict:
        """项目工作台一次性需要的全部数据。"""
        project = self.get(project_id)
        evidence = self.datasets.evidence(project_id) if self.datasets.has_dataset(project_id) else None
        return {'project': project.to_dict(),
                'evidence': evidence.to_dict() if evidence else None,
                'reports': [report.to_dict() for report in self.reports.list_for(project_id)]}

    def delete(self, project_id: str) -> None:
        self.get(project_id)
        self.projects.delete(project_id)
        self.reports.delete_for(project_id)
        self.data_store.drop(project_id)

class DatasetService:
    """矢量成果与项目资料的导入。"""

    def __init__(self, projects, data_store, default_crs: str = ''):
        self.projects = projects
        self.data_store = data_store
        self.default_crs = default_crs

    def import_vector(self, project_id: str, source: dict, label: str = '') -> Evidence:
        project = self.require_project(project_id)
        # 项目未填坐标系时用系统默认值兜底，避免报告出现空的空间参考。
        crs = project.coordinate_system or self.default_crs
        collection = gis.import_vector(source, crs)
        evidence = gis.calculate_evidence(collection, crs)
        if not evidence.feature_count:
            raise ValidationError('未解析到任何要素，请检查导出的成果文件')
        self.data_store.save_dataset(project_id, collection)
        project.dataset = DatasetInfo(source=label or '用户上传成果',
                                      format='shpzip' if source.get('format') == 'shpzip' else 'geojson',
                                      feature_count=evidence.feature_count, crs=evidence.crs)
        if not project.coordinate_system:
            project.coordinate_system = evidence.crs
        project.status = IMPORTED if project.status != REPORTED else project.status
        self.projects.save(project)
        return evidence

    def evidence(self, project_id: str) -> Evidence:
        project = self.require_project(project_id)
        return gis.calculate_evidence(self._dataset(project_id), project.coordinate_system or self.default_crs)

    def has_dataset(self, project_id: str) -> bool:
        return self.data_store.load_dataset(project_id) is not None

    def preview_svg(self, project_id: str) -> str:
        return gis.render_svg(self._dataset(project_id))

    def add_material(self, project_id: str, filename: str, content: str) -> Project:
        project = self.require_project(project_id)
        text = extract_text(filename, content)
        if not text.strip():
            raise ValidationError('该资料未提取到文本内容')
        materials = self.data_store.load_materials(project_id)
        materials.append({'filename': filename, 'text': text})
        self.data_store.save_materials(project_id, materials)
        project.materials.append(MaterialInfo(filename=filename, chars=len(text)))
        return self.projects.save(project)

    def material_text(self, project_id: str) -> str:
        blocks = [f"【{item['filename']}】\n{item['text']}" for item in self.data_store.load_materials(project_id)]
        return '\n\n'.join(blocks)

    def require_project(self, project_id: str) -> Project:
        project = self.projects.get(project_id)
        if not project:
            raise NotFoundError('项目不存在或已被删除')
        return project

    def _dataset(self, project_id: str) -> dict:
        dataset = self.data_store.load_dataset(project_id)
        if not dataset:
            raise ValidationError('该项目尚未导入矢量成果')
        return dataset

class ReportService:
    """报告生成用例：证据 → 叙述 → 排版 → 归档。"""

    def __init__(self, projects, datasets: DatasetService, reports, output_dir: Path,
                 generator: NarrativeGenerator | None = None):
        self.projects = projects
        self.datasets = datasets
        self.reports = reports
        self.output_dir = output_dir
        self.generator = generator or NarrativeGenerator()

    def generate(self, project_id: str, payload: dict, setting: LlmSetting) -> Report:
        payload = payload or {}
        project = self.datasets.require_project(project_id)
        template = get_template(payload.get('template'))
        evidence = self.datasets.evidence(project_id)
        description = str(payload.get('description') or '').strip()
        if description and description != project.description:
            project.description = description
            self.projects.save(project)
        narrative = self.generator.generate(project, evidence, description or project.description,
                                            self.datasets.material_text(project_id), setting)
        filename = f'{_safe_filename(project.name)}_{template.id}_{uuid4().hex[:8]}.docx'
        self.output_dir.mkdir(parents=True, exist_ok=True)
        render(project, evidence, narrative, template, self.output_dir / filename)
        report = Report(project_id=project_id, template=template.id, template_name=template.name,
                        filename=filename, mode=narrative.mode, source=narrative.source)
        self.reports.add(report)
        project.status = REPORTED
        self.projects.save(project)
        return report

    def list(self, project_id: str) -> list[Report]:
        return self.reports.list_for(project_id)
