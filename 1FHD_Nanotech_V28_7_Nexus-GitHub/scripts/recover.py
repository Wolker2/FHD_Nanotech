#!/usr/bin/env python3
"""Generate editable V28.7 source from the unchanged attached runtime archive."""
from pathlib import Path
from zipfile import ZipFile
import json,hashlib,sys
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'scripts'))
import dat_codec,gi_codec
archive=root/'install/FHD_Nanotech_V28_7_MARKET_APPEARANCE_TEST_RELEASE.zip'
source=root/'source'
manifest={}
with ZipFile(archive) as z:
 for variant in ('TEST','RELEASE'):
  prefix=f'{variant}/Mods/FHD_MODS/FHD_Nanotech/'
  for name in ['CFG/Main.dat','CFG/Rus/Lang.dat']:
   b=z.read(prefix+name);x=dat_codec.decode(b,'blockpar')
   assert dat_codec.encode(x)==b
   p=source/variant/(name+'.json');p.parent.mkdir(parents=True,exist_ok=True)
   p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
  b=z.read(prefix+'ModuleInfo.txt')
  assert b[:2]==b'\xff\xfe'
  text=b.decode('utf-16');assert text.encode('utf-16')==b
  p=source/variant/'ModuleInfo.utf8.txt'
  p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf-8')
  for name in z.namelist():
   if not name.startswith(prefix):continue
   b=z.read(name);manifest[name]={'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
   if not name.endswith('.gi'):continue
   rel=name.split('/DATA/Image/Frames/Tier1/')[1]
   p=source/'shared/graphics'/(rel+'.json')
   p.parent.mkdir(parents=True,exist_ok=True)
   if p.exists():assert gi_codec.encode(json.loads(p.read_text('utf-8')))==b
   else:
    x=gi_codec.decode(b);assert gi_codec.encode(x)==b
    p.write_text(json.dumps(x,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
 p=source/'original_build_nanotech_v28_7_market.py'
 p.write_bytes(z.read('SOURCE/build_nanotech_v28_7_market.py'))
(root/'original-file-sha256.json').write_text(json.dumps({'files':manifest},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Source recovery complete:',len(manifest),'original runtime files')
