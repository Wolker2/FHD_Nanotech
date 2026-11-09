#!/usr/bin/env python3
"""Build TEST and RELEASE install ZIPs from recovered editable sources."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
import hashlib,sys,json
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'scripts'))
import dat_codec,gi_codec
manifest=json.loads((root/'original-file-sha256.json').read_text('utf-8'))['files']
out=root/'dist';out.mkdir(exist_ok=True)
for variant in ('TEST','RELEASE'):
 prefix='Mods/FHD_MODS/FHD_Nanotech/'
 files={}
 for rel in ('CFG/Main.dat','CFG/Rus/Lang.dat'):
  x=json.loads((root/'source'/variant/(rel+'.json')).read_text('utf-8'))
  files[rel]=dat_codec.encode(x)
 files['ModuleInfo.txt']=(root/'source'/variant/'ModuleInfo.utf8.txt').read_text('utf-8').encode('utf-16')
 for p in (root/'source/shared/graphics').glob('*.json'):
  files['DATA/Image/Frames/Tier1/'+p.stem]=gi_codec.encode(json.loads(p.read_text('utf-8')))
 for rel,b in files.items():
  key=f'{variant}/'+prefix+rel
  assert hashlib.sha256(b).hexdigest()==manifest[key]['sha256'],key
 assert len(files)==len([x for x in manifest if x.startswith(variant+'/'+prefix)])
 dest=out/f'FHD_Nanotech_V28_7_{variant}_FROM_SOURCE.zip'
 with ZipFile(dest,'w',ZIP_DEFLATED) as z:
  for rel,b in sorted(files.items()):z.writestr(prefix+rel,b)
 print(variant,len(files),'files matched; built',dest)
