"""ESRI Shapefile 解析（MVP 子集：Point / PolyLine / Polygon）。

手写解析器只为保持零依赖；生产版建议替换为 pyshp / fiona，本模块对外只暴露
read_shapefile_zip，替换实现时不影响其他模块。
"""
import base64, io, struct, zipfile
from pathlib import Path

from ..domain import ValidationError

POINT, POLYLINE, POLYGON = 1, 3, 5

def _dbf_records(raw):
    """读取 Shapefile 附带的 dBase 属性表。"""
    if not raw: return []
    record_count, header_len, record_len = struct.unpack('<xxxxIHH20x', raw[:32])
    fields, offset = [], 32
    while offset < header_len and raw[offset] != 0x0D:
        name = raw[offset:offset+11].split(b'\0', 1)[0].decode('latin1').strip()
        fields.append((name, chr(raw[offset+11]), raw[offset+16])); offset += 32
    records = []
    for i in range(record_count):
        row = raw[header_len+i*record_len:header_len+(i+1)*record_len]
        if not row or row[:1] == b'*': continue
        pos, item = 1, {}
        for name, typ, width in fields:
            value = row[pos:pos+width].decode('gb18030', errors='replace').strip(); pos += width
            if typ in ('N', 'F') and value:
                try: value = float(value) if '.' in value else int(value)
                except ValueError: pass
            item[name.lower()] = value
        records.append(item)
    return records

def _parse_shp(raw, attributes, layer_name):
    if len(raw) < 100: raise ValidationError(f'{layer_name}.shp 文件无效或内容不完整')
    features, offset, index = [], 100, 0
    while offset + 8 <= len(raw):
        _, words = struct.unpack('>2i', raw[offset:offset+8]); offset += 8
        body = raw[offset:offset+words*2]; offset += words*2
        if len(body) < 4: continue
        kind = struct.unpack('<i', body[:4])[0]
        props = dict(attributes[index]) if index < len(attributes) else {}; index += 1
        props['layer'] = props.get('layer') or layer_name
        props['id'] = str(props.get('id') or props.get('name') or f'{layer_name}-{index:03d}')
        if kind == POINT:
            geometry = {'type': 'Point', 'coordinates': list(struct.unpack('<2d', body[4:20]))}
        elif kind in (POLYLINE, POLYGON):
            *_, parts, points = struct.unpack('<4d2i', body[4:44])
            starts = list(struct.unpack('<'+'i'*parts, body[44:44+4*parts])); start = 44+4*parts
            xy = [list(struct.unpack('<2d', body[start+i*16:start+(i+1)*16])) for i in range(points)]
            chunks = [xy[s:(starts[p+1] if p+1 < parts else len(xy))] for p, s in enumerate(starts)]
            if kind == POLYGON: geometry = {'type': 'Polygon', 'coordinates': chunks}
            elif len(chunks) == 1: geometry = {'type': 'LineString', 'coordinates': chunks[0]}
            else: geometry = {'type': 'MultiLineString', 'coordinates': chunks}
        else:
            continue  # 空要素与未支持的类型跳过，calculate_evidence 不会为其产生统计
        features.append({'type': 'Feature', 'properties': props, 'geometry': geometry})
    return features

def read_shapefile_zip(encoded: str, crs: str) -> dict:
    """把含 .shp/.dbf 的 ZIP 转成 GeoJSON FeatureCollection。"""
    try:
        archive = zipfile.ZipFile(io.BytesIO(base64.b64decode(encoded or '')))
    except Exception as exc:
        raise ValidationError('无法读取 ZIP，请确认压缩包包含 Shapefile 文件') from exc
    names = archive.namelist()
    shp_names = [n for n in names if n.lower().endswith('.shp')]
    if not shp_names: raise ValidationError('压缩包未找到 .shp 文件')
    features = []
    for shp_name in shp_names:
        base = shp_name.rsplit('.', 1)[0]
        dbf_name = next((n for n in names if n.rsplit('.', 1)[0].lower() == base.lower() and n.lower().endswith('.dbf')), None)
        attributes = _dbf_records(archive.read(dbf_name)) if dbf_name else []
        features.extend(_parse_shp(archive.read(shp_name), attributes, Path(base).name))
    return {'type': 'FeatureCollection', 'name': 'SHP 导入成果', 'features': features,
            'crs': {'type': 'name', 'properties': {'name': crs}}}
