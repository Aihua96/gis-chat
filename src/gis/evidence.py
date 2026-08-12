"""确定性统计与基础质检：报告中的一切数值都出自这里。"""
import math

from ..domain import Evidence, LayerStat

def _ring_area(coords):
    """多边形鞋带公式（投影平面坐标）。"""
    if len(coords) < 3: return 0.0
    return abs(sum(coords[i][0]*coords[(i+1) % len(coords)][1] - coords[(i+1) % len(coords)][0]*coords[i][1]
                   for i in range(len(coords))) / 2)

def _length(coords):
    return sum(math.hypot(coords[i+1][0]-coords[i][0], coords[i+1][1]-coords[i][1]) for i in range(len(coords)-1))

def bbox(geometry):
    points = []
    def walk(value):
        if isinstance(value, (list, tuple)) and value and isinstance(value[0], (int, float)): points.append(value)
        elif isinstance(value, (list, tuple)):
            for child in value: walk(child)
    walk(geometry.get('coordinates', []))
    if not points: return None
    return (min(p[0] for p in points), min(p[1] for p in points),
            max(p[0] for p in points), max(p[1] for p in points))

def calculate_evidence(data: dict, default_crs: str) -> Evidence:
    layers, warnings, seen_ids, polygons = {}, [], set(), []
    total_area = total_length = 0.0
    for index, feature in enumerate(data.get('features', []), 1):
        props = feature.get('properties') or {}
        geometry = feature.get('geometry') or {}
        stat = layers.setdefault(props.get('layer') or '未分类图层', LayerStat())
        stat.count += 1
        feature_id = props.get('id')
        if not feature_id: warnings.append(f'第 {index} 个要素缺少 id 属性')
        elif feature_id in seen_ids: warnings.append(f'要素编号重复：{feature_id}')
        else: seen_ids.add(feature_id)
        kind, coords = geometry.get('type'), geometry.get('coordinates', [])
        if kind == 'Polygon':
            area = _ring_area(coords[0]) - sum(_ring_area(hole) for hole in coords[1:]) if coords else 0.0
            stat.area += area; total_area += area
            polygons.append((feature_id or str(index), bbox(geometry)))
        elif kind == 'LineString':
            size = _length(coords); stat.length += size; total_length += size
        elif kind == 'MultiLineString':
            size = sum(_length(part) for part in coords); stat.length += size; total_length += size
        elif kind != 'Point':
            warnings.append(f'第 {index} 个要素为当前版本未支持的几何类型：{kind}')
        if props.get('quality') == '待复核':
            warnings.append(f'{feature_id or "未编号要素"} 标记为待复核')
    # 演示级 bbox 重叠检查：仅做预警，不能替代严格拓扑验证。
    for i, (left_id, left) in enumerate(polygons):
        for right_id, right in polygons[i+1:]:
            if left and right and max(left[0], right[0]) < min(left[2], right[2]) \
                    and max(left[1], right[1]) < min(left[3], right[3]):
                warnings.append(f'面要素包络可能重叠：{left_id} / {right_id}（需人工复核）')
    crs = (data.get('crs') or {}).get('properties', {}).get('name') or default_crs
    return Evidence(feature_count=len(data.get('features', [])), layers=layers, total_area=total_area,
                    total_length=total_length, warnings=warnings, crs=crs)
