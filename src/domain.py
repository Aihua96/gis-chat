"""领域模型与错误类型。

这一层是纯数据结构：不读写文件、不发起网络请求、不依赖 python-docx，
因此可以被任何上层（HTTP、CLI、批处理）复用，也便于单独测试。
"""
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime
from uuid import uuid4

def now() -> str:
    return datetime.now().isoformat(timespec='seconds')

def new_id(prefix: str) -> str:
    return f'{prefix}_{uuid4().hex[:10]}'

def _load(cls, raw: dict):
    """按数据类字段过滤后实例化，避免历史数据中的多余键导致启动失败。"""
    allowed = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in (raw or {}).items() if k in allowed})

class AppError(Exception):
    """可直接映射为 HTTP 响应的业务异常。"""
    status = 400

class ValidationError(AppError):
    status = 400

class NotFoundError(AppError):
    status = 404

class DependencyMissing(AppError):
    status = 503

class LlmError(AppError):
    status = 502

DRAFT, IMPORTED, REPORTED = 'draft', 'imported', 'reported'
STATUS_LABELS = {DRAFT: '待导入成果', IMPORTED: '成果已导入', REPORTED: '已生成报告'}

@dataclass
class MaterialInfo:
    filename: str
    chars: int
    uploaded_at: str = field(default_factory=now)

@dataclass
class DatasetInfo:
    source: str
    format: str
    feature_count: int
    crs: str
    imported_at: str = field(default_factory=now)

@dataclass
class Project:
    name: str
    type: str = ''
    location: str = ''
    coordinate_system: str = ''
    period: str = ''
    unit: str = ''
    instrument: str = ''
    description: str = ''
    id: str = field(default_factory=lambda: new_id('prj'))
    status: str = DRAFT
    dataset: DatasetInfo | None = None
    materials: list[MaterialInfo] = field(default_factory=list)
    created_at: str = field(default_factory=now)
    updated_at: str = field(default_factory=now)

    def touch(self):
        self.updated_at = now()

    def to_dict(self):
        data = asdict(self)
        data['status_label'] = STATUS_LABELS.get(self.status, self.status)
        return data

    @classmethod
    def from_dict(cls, raw: dict):
        raw = dict(raw or {})
        dataset, materials = raw.pop('dataset', None), raw.pop('materials', None) or []
        project = _load(cls, raw)
        project.dataset = _load(DatasetInfo, dataset) if dataset else None
        project.materials = [_load(MaterialInfo, item) for item in materials]
        return project

@dataclass
class LayerStat:
    count: int = 0
    area: float = 0.0
    length: float = 0.0

@dataclass
class Evidence:
    """GIS 引擎产出的确定性证据，是报告中所有数值的唯一来源。"""
    feature_count: int
    layers: dict[str, LayerStat]
    total_area: float
    total_length: float
    warnings: list[str]
    crs: str

    def to_dict(self):
        return asdict(self)

@dataclass
class Narrative:
    """报告的叙述性章节。mode 为 llm 或 template，source 是给用户看的生成方式说明。"""
    sections: dict[str, str]
    source: str
    mode: str

@dataclass
class Report:
    project_id: str
    template: str
    template_name: str
    filename: str
    mode: str
    source: str
    id: str = field(default_factory=lambda: new_id('rpt'))
    created_at: str = field(default_factory=now)

    def to_dict(self):
        return {**asdict(self), 'url': '/output/' + self.filename}

    @classmethod
    def from_dict(cls, raw: dict):
        return _load(cls, {k: v for k, v in (raw or {}).items() if k != 'url'})

@dataclass
class LlmSetting:
    base_url: str = ''
    model: str = ''
    api_key: str = ''

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.model)

    def public(self) -> dict:
        """对外只暴露地址与模型名；API Key 不落盘、不回显。"""
        return {'base_url': self.base_url, 'model': self.model, 'configured': self.configured}

    @classmethod
    def from_dict(cls, raw: dict):
        raw = raw or {}
        return cls(str(raw.get('base_url') or '').strip(),
                   str(raw.get('model') or '').strip(),
                   str(raw.get('api_key') or ''))
