"""HTTP 接口层：把请求翻译成服务层调用，再把结果与错误翻译成响应。

这一层不含业务规则；所有用例都在 services 中，因此换成 FastAPI / Flask
只需要重写本文件。
"""
import json, re, traceback
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from .domain import AppError, LlmSetting
from .reporting import DOCX_AVAILABLE, SUPPORTED_SUFFIXES, list_templates
from . import gis

CONTENT_TYPES = {'.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8',
                 '.js': 'application/javascript; charset=utf-8', '.svg': 'image/svg+xml',
                 '.geojson': 'application/geo+json', '.zip': 'application/zip',
                 '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}
STATIC_FILES = ('index.html', 'styles.css', 'app.js')
REPORT_FILENAME = re.compile(r'^[^/\\]+\.docx$')

@dataclass
class Response:
    status: int = 200
    body: bytes = b''
    content_type: str = 'application/json; charset=utf-8'
    headers: list = field(default_factory=list)

def json_response(payload, status=200) -> Response:
    return Response(status, json.dumps(payload, ensure_ascii=False).encode())

def file_response(path: Path, download_as: str = '') -> Response:
    if not path.is_file():
        return json_response({'error': '文件不存在'}, 404)
    headers = [('Content-Disposition', f'attachment; filename={download_as}')] if download_as else []
    return Response(200, path.read_bytes(), CONTENT_TYPES.get(path.suffix.lower(), 'application/octet-stream'), headers)

class Api:
    """路由表 + 请求处理。每个处理函数接收 (路径参数, 请求体) 并返回 Response。"""

    def __init__(self, projects, datasets, reports, settings, web_dir: Path, data_dir: Path, output_dir: Path):
        self.projects, self.datasets, self.reports, self.settings = projects, datasets, reports, settings
        self.web_dir, self.data_dir, self.output_dir = web_dir, data_dir, output_dir
        self.routes = [
            ('GET', r'/api/meta', self.meta),
            ('GET', r'/api/settings', self.read_settings),
            ('PUT', r'/api/settings', self.write_settings),
            ('GET', r'/api/projects', self.list_projects),
            ('POST', r'/api/projects', self.create_project),
            ('POST', r'/api/projects/demo', self.create_demo_project),
            ('GET', r'/api/projects/(?P<pid>[\w-]+)', self.project_detail),
            ('DELETE', r'/api/projects/(?P<pid>[\w-]+)', self.delete_project),
            ('POST', r'/api/projects/(?P<pid>[\w-]+)/dataset', self.import_dataset),
            ('GET', r'/api/projects/(?P<pid>[\w-]+)/preview\.svg', self.preview),
            ('POST', r'/api/projects/(?P<pid>[\w-]+)/materials', self.add_material),
            ('GET', r'/api/projects/(?P<pid>[\w-]+)/reports', self.list_reports),
            ('POST', r'/api/projects/(?P<pid>[\w-]+)/reports', self.create_report),
            ('GET', r'/api/demo\.geojson', self.demo_geojson),
            ('GET', r'/api/demo-shp\.zip', self.demo_shapefile),
            ('GET', r'/output/(?P<filename>.+)', self.download_report),
            ('GET', r'/(?P<name>index\.html|styles\.css|app\.js|)', self.static_file),
        ]
        self.compiled = [(method, re.compile(f'^{pattern}$'), handler) for method, pattern, handler in self.routes]

    def dispatch(self, method: str, raw_path: str, body: dict) -> Response:
        path = unquote(urlparse(raw_path).path)
        allowed = set()
        for route_method, pattern, handler in self.compiled:
            match = pattern.match(path)
            if not match:
                continue
            if route_method != method:
                allowed.add(route_method)
                continue
            try:
                return handler(match.groupdict(), body)
            except AppError as exc:
                return json_response({'error': str(exc)}, exc.status)
            except Exception as exc:  # 未预期错误：返回通用信息，细节留在服务端日志
                traceback.print_exc()
                return json_response({'error': f'服务内部错误：{exc}'}, 500)
        if allowed:
            return json_response({'error': f'该地址不支持 {method}'}, 405)
        return json_response({'error': '未找到资源'}, 404)

    # --- 元信息与设置 ---

    def meta(self, _params, _body):
        return json_response({'templates': list_templates(), 'material_suffixes': list(SUPPORTED_SUFFIXES),
                              'vector_formats': list(gis.SUPPORTED_FORMATS), 'docx_available': DOCX_AVAILABLE,
                              'settings': self.settings.load().public()})

    def read_settings(self, _params, _body):
        return json_response(self.settings.load().public())

    def write_settings(self, _params, body):
        return json_response(self.settings.save(LlmSetting.from_dict(body)).public())

    # --- 项目 ---

    def list_projects(self, _params, _body):
        return json_response({'projects': [project.to_dict() for project in self.projects.list()]})

    def create_project(self, _params, body):
        return json_response({'project': self.projects.create(body).to_dict()}, 201)

    def create_demo_project(self, _params, _body):
        return json_response({'project': self.projects.create_demo().to_dict()}, 201)

    def project_detail(self, params, _body):
        return json_response(self.projects.detail(params['pid']))

    def delete_project(self, params, _body):
        self.projects.delete(params['pid'])
        return json_response({'deleted': params['pid']})

    # --- 成果与资料 ---

    def import_dataset(self, params, body):
        body = body or {}
        evidence = self.datasets.import_vector(params['pid'], body.get('source') or {}, str(body.get('label') or ''))
        return json_response({'evidence': evidence.to_dict(),
                              'project': self.datasets.require_project(params['pid']).to_dict()})

    def preview(self, params, _body):
        svg = self.datasets.preview_svg(params['pid'])
        return Response(200, svg.encode(), CONTENT_TYPES['.svg'], [('Cache-Control', 'no-store')])

    def add_material(self, params, body):
        body = body or {}
        project = self.datasets.add_material(params['pid'], str(body.get('filename') or ''), body.get('content') or '')
        return json_response({'project': project.to_dict()})

    # --- 报告 ---

    def list_reports(self, params, _body):
        return json_response({'reports': [report.to_dict() for report in self.reports.list(params['pid'])]})

    def create_report(self, params, body):
        body = body or {}
        report = self.reports.generate(params['pid'], body, self._resolve_setting(body))
        return json_response({'report': report.to_dict()}, 201)

    def _resolve_setting(self, body: dict) -> LlmSetting:
        """请求中的地址/模型优先，未填则用已保存的设置；API Key 只来自本次请求。"""
        stored, requested = self.settings.load(), LlmSetting.from_dict(body.get('llm'))
        return LlmSetting(base_url=requested.base_url or stored.base_url,
                          model=requested.model or stored.model, api_key=requested.api_key)

    # --- 静态资源与示例数据 ---

    def demo_geojson(self, _params, _body):
        return file_response(self.data_dir / 'demo_project.geojson')

    def demo_shapefile(self, _params, _body):
        return file_response(self.data_dir / 'demo_engineering_survey_shp.zip', 'demo_engineering_survey_shp.zip')

    def download_report(self, params, _body):
        name = params['filename']
        if not REPORT_FILENAME.match(name):
            return json_response({'error': '文件名不合法'}, 400)
        return file_response(self.output_dir / name)

    def static_file(self, params, _body):
        name = params['name'] or 'index.html'
        if name not in STATIC_FILES:
            return json_response({'error': '未找到资源'}, 404)
        return file_response(self.web_dir / name)

def make_handler(api: Api, max_body: int):
    class Handler(BaseHTTPRequestHandler):
        server_version = 'SurveyReportServer'

        def _respond(self, response: Response):
            self.send_response(response.status)
            self.send_header('Content-Type', response.content_type)
            self.send_header('Content-Length', str(len(response.body)))
            for key, value in response.headers:
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(response.body)

        def _handle(self, method):
            try:
                length = int(self.headers.get('Content-Length', '0') or 0)
            except ValueError:
                return self._respond(json_response({'error': 'Content-Length 不合法'}, 400))
            if length > max_body:
                return self._respond(json_response({'error': '请求体过大'}, 413))
            body = {}
            if length > 0:
                try:
                    body = json.loads(self.rfile.read(length))
                except Exception:
                    return self._respond(json_response({'error': '请求数据无法解析'}, 400))
            self._respond(api.dispatch(method, self.path, body))

        def do_GET(self): self._handle('GET')
        def do_POST(self): self._handle('POST')
        def do_PUT(self): self._handle('PUT')
        def do_DELETE(self): self._handle('DELETE')

    return Handler

def serve(api: Api, host: str, port: int, max_body: int):
    ThreadingHTTPServer((host, port), make_handler(api, max_body)).serve_forever()
