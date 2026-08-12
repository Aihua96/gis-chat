"""Deterministic GIS import, evidence calculation and lightweight visual preview."""
import base64, io, math, struct, zipfile
from pathlib import Path
from xml.sax.saxutils import escape

def _dbf_records(raw):
    if not raw: return []
    record_count, header_len, record_len = struct.unpack('<xxxxIHH20x', raw[:32]); fields=[]; offset=32
    while offset < header_len and raw[offset] != 0x0D:
        name=raw[offset:offset+11].split(b'\0',1)[0].decode('latin1').strip(); fields.append((name, chr(raw[offset+11]), raw[offset+16])); offset+=32
    result=[]
    for i in range(record_count):
        row=raw[header_len+i*record_len:header_len+(i+1)*record_len]
        if not row or row[:1]==b'*': continue
        pos=1; item={}
        for name, typ, width in fields:
            value=row[pos:pos+width].decode('gb18030',errors='replace').strip(); pos+=width
            if typ in ('N','F') and value:
                try: value=float(value) if '.' in value else int(value)
                except ValueError: pass
            item[name.lower()]=value
        result.append(item)
    return result

def _parse_shp(raw, attributes, layer_name):
    if len(raw)<100: raise ValueError(f'{layer_name}.shp 文件无效或内容不完整')
    features=[]; offset=100; index=0
    while offset+8<=len(raw):
        _,words=struct.unpack('>2i',raw[offset:offset+8]); offset+=8; body=raw[offset:offset+words*2]; offset+=words*2
        if len(body)<4: continue
        kind=struct.unpack('<i',body[:4])[0]; prop=dict(attributes[index]) if index<len(attributes) else {}; index+=1
        prop['layer']=prop.get('layer') or layer_name; prop['id']=str(prop.get('id') or prop.get('name') or f'{layer_name}-{index:03d}')
        if kind==0: continue
        if kind==1:
            geometry={'type':'Point','coordinates':list(struct.unpack('<2d',body[4:20]))}
        elif kind in (3,5):
            *_,parts,points=struct.unpack('<4d2i',body[4:44]); starts=list(struct.unpack('<'+'i'*parts,body[44:44+4*parts])); start=44+4*parts
            xy=[list(struct.unpack('<2d',body[start+i*16:start+(i+1)*16])) for i in range(points)]
            chunks=[xy[s:(starts[p+1] if p+1<parts else len(xy))] for p,s in enumerate(starts)]
            geometry={'type':'LineString','coordinates':chunks[0]} if kind==3 and len(chunks)==1 else ({'type':'MultiLineString','coordinates':chunks} if kind==3 else {'type':'Polygon','coordinates':chunks})
        else: continue
        features.append({'type':'Feature','properties':prop,'geometry':geometry})
    return features

def import_shp_zip(encoded, crs):
    try: archive=zipfile.ZipFile(io.BytesIO(base64.b64decode(encoded)))
    except Exception as exc: raise ValueError('无法读取 ZIP，请确认压缩包包含 Shapefile 文件') from exc
    names=archive.namelist(); shp_names=[n for n in names if n.lower().endswith('.shp')]
    if not shp_names: raise ValueError('压缩包未找到 .shp 文件')
    features=[]
    for shp_name in shp_names:
        base=shp_name.rsplit('.',1)[0]; dbf_name=next((n for n in names if n.rsplit('.',1)[0].lower()==base.lower() and n.lower().endswith('.dbf')),None)
        features.extend(_parse_shp(archive.read(shp_name),_dbf_records(archive.read(dbf_name)) if dbf_name else [],Path(base).name))
    return {'type':'FeatureCollection','name':'SHP 导入成果','features':features,'crs':{'type':'name','properties':{'name':crs}}}

def _ring_area(coords): return abs(sum(coords[i][0]*coords[(i+1)%len(coords)][1]-coords[(i+1)%len(coords)][0]*coords[i][1] for i in range(len(coords)))/2) if len(coords)>=3 else 0.0
def _length(coords): return sum(math.hypot(coords[i+1][0]-coords[i][0],coords[i+1][1]-coords[i][1]) for i in range(len(coords)-1))
def _bbox(geometry):
    points=[]
    def walk(v):
        if isinstance(v,(list,tuple)) and v and isinstance(v[0],(int,float)): points.append(v)
        elif isinstance(v,(list,tuple)):
            for child in v: walk(child)
    walk(geometry.get('coordinates',[]))
    return (min(x[0] for x in points),min(x[1] for x in points),max(x[0] for x in points),max(x[1] for x in points)) if points else None

def calculate_evidence(data, default_crs):
    """确定性统计：要素数、分图层面积/长度，以及基础质检预警。数值口径见报告“数据来源与处理口径”。"""
    layers,warnings,ids,polygons={},[],set(),[]; total_area=total_length=0.0
    for index,feature in enumerate(data.get('features',[]),1):
        props,geom=feature.get('properties') or {},feature.get('geometry') or {}; layer=props.get('layer') or '未分类图层'; item=layers.setdefault(layer,{'count':0,'area':0.0,'length':0.0}); item['count']+=1
        fid=props.get('id')
        if not fid: warnings.append(f'第 {index} 个要素缺少 id 属性')
        elif fid in ids: warnings.append(f'要素编号重复：{fid}')
        else: ids.add(fid)
        typ,c=geom.get('type'),geom.get('coordinates',[])
        if typ=='Polygon':
            area=_ring_area(c[0])-sum(_ring_area(x) for x in c[1:]); item['area']+=area; total_area+=area; polygons.append((fid or str(index),_bbox(geom)))
        elif typ=='LineString': item['length']+=_length(c); total_length+=_length(c)
        elif typ=='MultiLineString':
            size=sum(_length(x) for x in c); item['length']+=size; total_length+=size
        elif typ!='Point': warnings.append(f'第 {index} 个要素为当前版本未支持的几何类型：{typ}')
        if props.get('quality')=='待复核': warnings.append(f'{fid or "未编号要素"} 标记为待复核')
    # 演示级 bbox 重叠检查：仅做预警，不能替代严格拓扑验证。
    for i,(id1,a) in enumerate(polygons):
        for id2,b in polygons[i+1:]:
            if a and b and max(a[0],b[0])<min(a[2],b[2]) and max(a[1],b[1])<min(a[3],b[3]): warnings.append(f'面要素包络可能重叠：{id1} / {id2}（需人工复核）')
    return {'feature_count':len(data.get('features',[])),'layers':layers,'total_area':total_area,'total_length':total_length,'warnings':warnings,'crs':(data.get('crs') or {}).get('properties',{}).get('name') or default_crs}

LAYER_COLORS = {'项目范围':'#2e73b8','道路中心线':'#e76f51','控制点':'#264653','绿化边界':'#65a30d'}

def render_preview(data):
    """把矢量成果渲染为 SVG 示意图。属性值来自上传文件，一律转义后再写入标记。"""
    extent=_bbox({'coordinates':[f.get('geometry',{}).get('coordinates',[]) for f in data.get('features',[])]})
    if not extent: return '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="430"></svg>'
    x0,y0,x1,y1=extent; dx,dy=max(x1-x0,1),max(y1-y0,1)
    def project(pt): return ((pt[0]-x0)/dx*700+50, 380-(pt[1]-y0)/dy*320)
    def path(points): return ' '.join(f'{a:.1f},{b:.1f}' for a,b in map(project,points))
    shape=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 430"><rect width="800" height="430" fill="#f6f8fb"/>'
           '<text x="50" y="32" font-family="Arial" font-size="16" fill="#0f2747">测区成果示意图（自动生成）</text>']
    for feature in data.get('features',[]):
        geom,props=feature.get('geometry') or {},feature.get('properties') or {}
        color=LAYER_COLORS.get(props.get('layer'),'#64748b'); typ,c=geom.get('type'),geom.get('coordinates',[])
        if typ=='Polygon' and c:
            shape.append(f'<polygon points="{path(c[0])}" fill="{color}" fill-opacity=".12" stroke="{color}" stroke-width="2"/>')
        elif typ=='LineString':
            shape.append(f'<polyline points="{path(c)}" fill="none" stroke="{color}" stroke-width="5" stroke-linecap="round"/>')
        elif typ=='MultiLineString':
            for part in c: shape.append(f'<polyline points="{path(part)}" fill="none" stroke="{color}" stroke-width="5" stroke-linecap="round"/>')
        elif typ=='Point' and c:
            a,b=project(c); label=escape(str(props.get('id','')))
            shape.append(f'<circle cx="{a:.1f}" cy="{b:.1f}" r="6" fill="{color}"/><text x="{a+8:.1f}" y="{b-8:.1f}" font-family="Arial" font-size="11" fill="#243b53">{label}</text>')
    shape.append('<text x="50" y="410" font-family="Arial" font-size="11" fill="#52616b">蓝：测区边界　红：道路中心线　绿：绿化边界　深色点：控制点</text></svg>')
    return ''.join(shape)
