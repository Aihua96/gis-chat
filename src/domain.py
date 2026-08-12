from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

@dataclass
class Project:
    id: str
    name: str
    project_type: str
    location: str = ''
    coordinate_system: str = ''
    description: str = ''
    status: str = 'draft'
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec='seconds'))
    def to_dict(self): return asdict(self)

@dataclass
class ReportRequest:
    project_id: str
    template: str
    description: str
    material: str
    vector_data: dict[str, Any]
    llm: dict[str, str]
