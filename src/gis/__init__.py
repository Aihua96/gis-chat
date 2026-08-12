"""GIS 引擎：矢量成果导入、确定性统计与示意图渲染。

上层只依赖这里导出的三个函数，内部解析实现可以整体替换。
"""
from ..domain import ValidationError
from .evidence import calculate_evidence
from .preview import render_svg
from .shapefile import read_shapefile_zip

SUPPORTED_FORMATS = ('geojson', 'shpzip')

def import_vector(source, crs: str) -> dict:
    """把上传内容归一化成 GeoJSON FeatureCollection。

    接受两种输入：{'format': 'shpzip', 'content': <base64>} 或直接的 FeatureCollection。
    """
    if not isinstance(source, dict):
        raise ValidationError('矢量成果格式无法识别，请上传 GeoJSON 或 Shapefile ZIP')
    if source.get('format') == 'shpzip':
        return read_shapefile_zip(source.get('content'), crs)
    features = source.get('features')
    if not isinstance(features, list):
        raise ValidationError('GeoJSON 缺少 features 数组，请确认导出的是 FeatureCollection')
    return {'type': 'FeatureCollection', 'name': source.get('name') or 'GeoJSON 导入成果',
            'features': features, 'crs': source.get('crs') or {'type': 'name', 'properties': {'name': crs}}}

__all__ = ['import_vector', 'calculate_evidence', 'render_svg', 'read_shapefile_zip', 'SUPPORTED_FORMATS']
