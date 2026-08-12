"""集中存放演示项目元数据与路径常量，便于后续替换为项目库读取。"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
OUTPUT = ROOT / 'output'
WEB = ROOT / 'web'

# 报告正文字体。macOS 演示环境使用 Heiti SC；其他环境或客户模板可改为已授权的中文字体。
REPORT_FONT = 'Heiti SC'

PROJECT = {
    'name': '新城产业园西侧配套道路竣工测量项目',
    'type': '工程测量（道路竣工测量）',
    'location': '四川省成都市新城产业园',
    'period': '2026年7月15日—2026年7月22日',
    'coordinate_system': 'CGCS2000 / 3度分带高斯-克吕格投影（37带）',
    'unit': '四川地质十一队（演示）',
    'instrument': 'GNSS 接收机、全站仪、无人机航测系统',
}
