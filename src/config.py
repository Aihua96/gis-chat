"""应用配置：路径、默认参数与演示项目种子。"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
WEB = ROOT / 'web'
OUTPUT = ROOT / 'output'
RUNTIME = ROOT / 'runtime'

HOST = '127.0.0.1'
PORT = 8080
VERSION = '0.4'
MAX_BODY = 64 * 1024 * 1024

DEFAULT_CRS = 'CGCS2000 / 3度分带高斯-克吕格投影（37带）'
MATERIAL_LIMIT = 30000
LLM_TIMEOUT = 90

# 报告正文字体。macOS 演示环境使用 Heiti SC；其他环境可改为本地已授权的中文字体。
REPORT_FONT = 'Heiti SC'

# “创建示例项目”使用的种子数据，配合 data/demo_project.geojson 让用户一键跑通流程。
DEMO_PROJECT = {
    'name': '新城产业园西侧配套道路竣工测量项目',
    'type': '工程测量（道路竣工测量）',
    'location': '四川省成都市新城产业园',
    'period': '2026年7月15日—2026年7月22日',
    'coordinate_system': DEFAULT_CRS,
    'unit': '四川地质十一队（演示）',
    'instrument': 'GNSS 接收机、全站仪、无人机航测系统',
    'description': '请编制本项目道路竣工测量技术总结，重点说明成果统计、质量情况和需复核事项。',
}
