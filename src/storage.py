"""基于 JSON 文件的仓储层。

刻意保持最小接口：生产环境用数据库实现同名方法即可替换，服务层无需改动。
ThreadingHTTPServer 是多线程的，所有写入都在锁内完成并采用临时文件替换，避免半写文件。
"""
import json, os, threading
from pathlib import Path

from .domain import LlmSetting, Project, Report

class JsonFile:
    """带锁的小型 JSON 文档，读写整份内容。"""

    def __init__(self, path: Path, default):
        self.path = path
        self.default = default
        self.lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def read(self):
        if not self.path.exists():
            return json.loads(json.dumps(self.default))
        try:
            return json.loads(self.path.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, OSError):
            return json.loads(json.dumps(self.default))

    def write(self, value):
        temp = self.path.with_suffix(self.path.suffix + '.tmp')
        temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(temp, self.path)

    def update(self, mutate):
        """在锁内完成 读-改-写，mutate 接收当前内容并原地修改。"""
        with self.lock:
            value = self.read()
            result = mutate(value)
            self.write(value)
            return result

class ProjectRepository:
    def __init__(self, root: Path):
        self.store = JsonFile(root / 'projects.json', {})

    def save(self, project: Project) -> Project:
        project.touch()
        self.store.update(lambda data: data.__setitem__(project.id, project.to_dict()))
        return project

    def get(self, project_id: str) -> Project | None:
        raw = self.store.read().get(project_id)
        return Project.from_dict(raw) if raw else None

    def list(self) -> list[Project]:
        projects = [Project.from_dict(raw) for raw in self.store.read().values()]
        return sorted(projects, key=lambda p: p.created_at, reverse=True)

    def delete(self, project_id: str) -> None:
        self.store.update(lambda data: data.pop(project_id, None))

class ReportRepository:
    def __init__(self, root: Path):
        self.store = JsonFile(root / 'reports.json', {})

    def add(self, report: Report) -> Report:
        self.store.update(lambda data: data.__setitem__(report.id, report.to_dict()))
        return report

    def list_for(self, project_id: str) -> list[Report]:
        reports = [Report.from_dict(raw) for raw in self.store.read().values() if raw.get('project_id') == project_id]
        return sorted(reports, key=lambda r: r.created_at, reverse=True)

    def delete_for(self, project_id: str) -> None:
        def mutate(data):
            for key in [k for k, v in data.items() if v.get('project_id') == project_id]:
                data.pop(key)
        self.store.update(mutate)

class ProjectDataStore:
    """项目下的大体量数据（矢量成果、资料全文）按项目分文件存放，避免撑大项目列表。"""

    def __init__(self, root: Path):
        self.root = root / 'projects'
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()

    def _path(self, project_id: str, kind: str) -> Path:
        return self.root / f'{project_id}.{kind}.json'

    def _read(self, project_id: str, kind: str, default):
        path = self._path(project_id, kind)
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, OSError):
            return default

    def _write(self, project_id: str, kind: str, value):
        with self.lock:
            path = self._path(project_id, kind)
            temp = path.with_suffix('.tmp')
            temp.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
            os.replace(temp, path)

    def save_dataset(self, project_id: str, feature_collection: dict) -> None:
        self._write(project_id, 'dataset', feature_collection)

    def load_dataset(self, project_id: str) -> dict | None:
        return self._read(project_id, 'dataset', None)

    def save_materials(self, project_id: str, materials: list) -> None:
        self._write(project_id, 'materials', materials)

    def load_materials(self, project_id: str) -> list:
        return self._read(project_id, 'materials', [])

    def drop(self, project_id: str) -> None:
        for kind in ('dataset', 'materials'):
            self._path(project_id, kind).unlink(missing_ok=True)

class SettingsStore:
    """模型接入配置。只持久化地址与模型名，API Key 不落盘。"""

    def __init__(self, root: Path):
        self.store = JsonFile(root / 'settings.json', {'base_url': '', 'model': ''})

    def load(self) -> LlmSetting:
        raw = self.store.read()
        return LlmSetting(base_url=raw.get('base_url', ''), model=raw.get('model', ''))

    def save(self, setting: LlmSetting) -> LlmSetting:
        self.store.update(lambda data: data.update({'base_url': setting.base_url, 'model': setting.model}))
        return self.load()
