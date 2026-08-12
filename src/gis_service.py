"""Deterministic GIS import, evidence calculation and lightweight visual preview."""
import base64, io, math, struct, zipfile
from pathlib import Path

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
    for i,(id1,a) in enumerate(polygons):
        for id2,b in polygons[i+1:]:
            if a and b and max(a[0],b[0])<min(a[2],b[2]) and max(a[1],b[1])<min(a[3],b[3]): warnings.append(f'面要素包络可能重叠：{id1} / {id2}（需人工复核）')
    return {'feature_count':len(data.get('features',[])),'layers':layers,'total_area':total_area,'total_length':total_length,'warnings':warnings,'crs':(data.get('crs') or {}).get('properties',{}).get('name') or default_crs}
