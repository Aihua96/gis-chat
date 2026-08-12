"""A replaceable local repository. Production can implement the same interface with PostgreSQL."""
import json
from pathlib import Path
from .domain import Project

class ProjectRepository:
    def __init__(self, root: Path):
        self.path = root / 'runtime' / 'projects.json'; self.path.parent.mkdir(exist_ok=True)
        if not self.path.exists(): self.path.write_text('{}', encoding='utf-8')
    def _read(self): return json.loads(self.path.read_text(encoding='utf-8'))
    def _write(self, value): self.path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    def save(self, project: Project):
        data=self._read(); data[project.id]=project.to_dict(); self._write(data); return project
    def get(self, project_id: str):
        data=self._read().get(project_id)
        return Project(**data) if data else None
    def list(self): return [Project(**x) for x in self._read().values()]
