#!/usr/bin/env python3
"""Create a small multi-layer Shapefile ZIP from the built-in GeoJSON sample."""
from pathlib import Path
import json, struct, zipfile

ROOT = Path(__file__).resolve().parents[1]

def dbf(rows):
    fields=[('LAYER','C',32),('ID','C',16),('NAME','C',40),('QUALITY','C',12)]
    header_len=32+32*len(fields)+1; record_len=1+sum(f[2] for f in fields)
    head=bytearray(struct.pack('<BBBBIHH20x',3,26,8,12,len(rows),header_len,record_len))
    for name,typ,width in fields:
        head.extend(name.encode()+b'\0'*(11-len(name))); head.extend(typ.encode()); head.extend(b'\0'*4); head.extend(bytes([width,0])); head.extend(b'\0'*14)
    head.extend(b'\r'); body=bytearray()
    for p in rows:
        body.extend(b' ')
        for name,_,width in fields:
            v=str(p.get(name.lower(), '')).encode('gb18030', errors='replace')[:width]
            body.extend(v+b' '*(width-len(v)))
    return bytes(head+body+b'\x1a')

def shp(features, typ):
    records=[]; bounds=[]
    for f in features:
        c=f['geometry']['coordinates']; parts=[c] if typ==3 else c
        pts=[c] if typ==1 else [p for part in parts for p in part]
        xs,ys=zip(*pts); bounds.extend(pts)
        if typ==1: body=struct.pack('<idd',1,*c)
        else:
            starts=[]; flattened=[]
            for part in parts: starts.append(len(flattened)); flattened.extend(part)
            body=struct.pack('<i4d2i',typ,min(xs),min(ys),max(xs),max(ys),len(parts),len(flattened))
            body+=struct.pack('<'+'i'*len(starts),*starts)
            body+=b''.join(struct.pack('<2d',*p) for p in flattened)
        records.append(body)
    xs,ys=zip(*bounds); length_words=(100+sum(8+len(r) for r in records))//2
    header=struct.pack('>i5i',9994,0,0,0,0,0)+struct.pack('>i',length_words)+struct.pack('<2i4d4d',1000,typ,min(xs),min(ys),max(xs),max(ys),0,0,0,0)
    raw=bytearray(header)
    for i,r in enumerate(records,1): raw.extend(struct.pack('>2i',i,len(r)//2)); raw.extend(r)
    return bytes(raw)

def main():
    data=json.loads((ROOT/'data/demo_project.geojson').read_text()); groups={}
    for f in data['features']:
        geom=f['geometry']['type']; typ={'Point':1,'LineString':3,'Polygon':5}[geom]
        groups.setdefault((f['properties']['layer'],typ),[]).append(f)
    dest=ROOT/'data/demo_engineering_survey_shp.zip'
    with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as z:
        for group_index, ((name,typ), items) in enumerate(groups.items(), 1):
            safe='layer_'+str(group_index)
            z.writestr(safe+'.shp',shp(items,typ)); z.writestr(safe+'.dbf',dbf([x['properties'] for x in items]))
            z.writestr(safe+'.prj','PROJCS["CGCS2000 / 3-degree Gauss-Kruger zone 37"]')
    print(dest)
if __name__=='__main__': main()
