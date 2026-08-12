#!/usr/bin/env python3
"""零依赖 Web MVP：工程测量矢量成果到技术总结报告。

本文件只负责 HTTP 路由与请求校验；GIS 计算、模型调用与文档排版分别位于 src/ 下的模块。
"""
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, unquote
import json, re, uuid

from src.config import DATA, OUTPUT, PROJECT, WEB
from src.documents import build_report, extract_material
from src.gis_service import calculate_evidence, import_shp_zip, render_preview
from src.llm import compose_sections

HOST, PORT = '127.0.0.1', 8080
MAX_BODY = 64 * 1024 * 1024
REPORT_NAME = re.compile(r'^[^/\\]+\.docx$')
DOCX_TYPE = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'

OUTPUT.mkdir(exist_ok=True)

def load_demo():
    return json.loads((DATA/'demo_project.geojson').read_text(encoding='utf-8'))

def to_geojson(payload):
    """请求体可以直接是 GeoJSON，也可以是 {format:'shpzip', content:<base64>}。"""
    source = payload.get('data', payload)
    if source.get('format') == 'shpzip':
        return import_shp_zip(source['content'], PROJECT['coordinate_system'])
    return source

class Handler(BaseHTTPRequestHandler):
    server_version = 'SurveyReportMVP/0.3'

    def send_payload(self, content, content_type, status=200, headers=()):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(content)))
        for key, value in headers: self.send_header(key, value)
        self.end_headers()
        self.wfile.write(content)

    def send_json(self, payload, status=200):
        self.send_payload(json.dumps(payload, ensure_ascii=False).encode(), 'application/json; charset=utf-8', status)

    def send_file(self, path: Path, content_type, headers=()):
        if not path.is_file(): return self.send_json({'error': '文件不存在'}, 404)
        self.send_payload(path.read_bytes(), content_type, headers=headers)

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path == '/api/project':
            return self.send_json({**PROJECT, 'analysis': calculate_evidence(load_demo(), PROJECT['coordinate_system'])})
        if path == '/api/preview.svg':
            return self.send_payload(render_preview(load_demo()).encode(), 'image/svg+xml')
        if path == '/api/demo.geojson':
            return self.send_file(DATA/'demo_project.geojson', 'application/geo+json')
        if path == '/api/demo-shp.zip':
            return self.send_file(DATA/'demo_engineering_survey_shp.zip', 'application/zip',
                                  [('Content-Disposition', 'attachment; filename=demo_engineering_survey_shp.zip')])
        if path.startswith('/output/'):
            # 只暴露本服务生成的报告，不做目录遍历。
            name = path[len('/output/'):]
            if not REPORT_NAME.match(name): return self.send_json({'error': '文件名不合法'}, 400)
            return self.send_file(OUTPUT/name, DOCX_TYPE)
        if path in ('/', '/index.html'):
            return self.send_file(WEB/'index.html', 'text/html; charset=utf-8')
        return self.send_json({'error': '未找到资源'}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get('Content-Length', '0'))
        if length > MAX_BODY: return self.send_json({'error': '请求体过大'}, 413)
        try: payload = json.loads(self.rfile.read(length))
        except Exception: return self.send_json({'error': '请求数据无法解析'}, 400)
        if path == '/api/extract-material':
            try: return self.send_json({'text': extract_material(payload['filename'], payload['content'])})
            except Exception as exc: return self.send_json({'error': str(exc)}, 400)
        if path not in ('/api/convert', '/api/analyse', '/api/report'):
            return self.send_json({'error': '未找到接口'}, 404)
        try: data = to_geojson(payload)
        except Exception as exc: return self.send_json({'error': str(exc)}, 400)
        if path == '/api/convert':
            return self.send_json(data)
        if path == '/api/analyse':
            return self.send_json({'analysis': calculate_evidence(data, PROJECT['coordinate_system']),
                                   'preview_svg': render_preview(data)})
        try:
            config = payload.get('llm') or {}
            evidence = calculate_evidence(data, PROJECT['coordinate_system'])
            sections, ai_status = compose_sections(evidence, payload.get('description', ''), payload.get('material', ''), config)
            name = '工程测量技术报告_'+uuid.uuid4().hex[:8]+'.docx'
            build_report(evidence, sections, ai_status, OUTPUT/name, payload.get('template', 'engineering_summary'))
            return self.send_json({'url': '/output/'+name, 'mode': 'llm' if config.get('base_url') else 'demo'})
        except Exception as exc:
            return self.send_json({'error': str(exc)}, 500)

if __name__ == '__main__':
    print(f'MVP started: http://{HOST}:{PORT}')
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
