"""把矢量成果渲染为 SVG 测区示意图。"""
from xml.sax.saxutils import escape

from .evidence import bbox

LAYER_COLORS = {'项目范围': '#2e73b8', '道路中心线': '#e76f51', '控制点': '#264653', '绿化边界': '#65a30d'}
DEFAULT_COLOR = '#64748b'
EMPTY_SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 430"><rect width="800" height="430" fill="#f6f8fb"/>' \
            '<text x="50" y="215" font-family="Arial" font-size="15" fill="#7b8a9a">暂无可绘制的矢量成果</text></svg>'

def render_svg(data: dict) -> str:
    """属性值来自上传文件，一律转义后再写入标记。"""
    extent = bbox({'coordinates': [f.get('geometry', {}).get('coordinates', []) for f in data.get('features', [])]})
    if not extent: return EMPTY_SVG
    x0, y0, x1, y1 = extent
    dx, dy = max(x1-x0, 1), max(y1-y0, 1)
    def project(point): return ((point[0]-x0)/dx*700+50, 380-(point[1]-y0)/dy*320)
    def path(points): return ' '.join(f'{x:.1f},{y:.1f}' for x, y in map(project, points))
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 430">'
             '<rect width="800" height="430" fill="#f6f8fb"/>'
             '<text x="50" y="32" font-family="Arial" font-size="16" fill="#0f2747">测区成果示意图（自动生成）</text>']
    for feature in data.get('features', []):
        geometry, props = feature.get('geometry') or {}, feature.get('properties') or {}
        color = LAYER_COLORS.get(props.get('layer'), DEFAULT_COLOR)
        kind, coords = geometry.get('type'), geometry.get('coordinates', [])
        if kind == 'Polygon' and coords:
            parts.append(f'<polygon points="{path(coords[0])}" fill="{color}" fill-opacity=".12" stroke="{color}" stroke-width="2"/>')
        elif kind == 'LineString' and coords:
            parts.append(f'<polyline points="{path(coords)}" fill="none" stroke="{color}" stroke-width="5" stroke-linecap="round"/>')
        elif kind == 'MultiLineString':
            for segment in coords:
                parts.append(f'<polyline points="{path(segment)}" fill="none" stroke="{color}" stroke-width="5" stroke-linecap="round"/>')
        elif kind == 'Point' and coords:
            x, y = project(coords)
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6" fill="{color}"/>'
                         f'<text x="{x+8:.1f}" y="{y-8:.1f}" font-family="Arial" font-size="11" fill="#243b53">'
                         f'{escape(str(props.get("id", "")))}</text>')
    parts.append('<text x="50" y="410" font-family="Arial" font-size="11" fill="#52616b">'
                 '蓝：测区边界　红：道路中心线　绿：绿化边界　深色点：控制点</text></svg>')
    return ''.join(parts)
