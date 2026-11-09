#!/usr/bin/env python3
"""Join original RAR5 file fragments and verify its SHA-256; no game changes."""
from pathlib import Path
import argparse,hashlib,json
ROOT=Path(__file__).resolve().parents[1]
def restore(folder='install/parts',metadata='install/parts.json',output=None):
 info=json.loads((ROOT/metadata).read_text('utf-8'))
 target=Path(output) if output else ROOT/'dist'/info['original_name']
 target.parent.mkdir(parents=True,exist_ok=True)
 # The unchanged RAR can be downloaded from the published Drive asset.
 local=ROOT/'install'/info['original_name']
 if local.exists():
  datahash=hashlib.sha256()
  with local.open('rb') as src:
   for chunk in iter(lambda:src.read(1048576),b''):datahash.update(chunk)
  if local.stat().st_size!=info['original_size'] or datahash.hexdigest()!=info['original_sha256']:
   raise ValueError('Original RAR checksum mismatch: '+str(local))
  return local
 if not (ROOT/folder/'000.part').exists():
  raise FileNotFoundError('Download the original RAR from the README into install/'+info['original_name'])
 digest=hashlib.sha256();written=0
 with target.open('wb') as out:
  for i,expected in enumerate(info['parts']):
   part=ROOT/folder/(f'{i:03}.part')
   data=part.read_bytes()
   if len(data)!=expected['size'] or hashlib.sha256(data).hexdigest()!=expected['sha256']:
    raise ValueError('Missing/modified part: '+str(part))
   digest.update(data);written+=len(data);out.write(data)
 if written!=info['original_size'] or digest.hexdigest()!=info['original_sha256']:
  target.unlink(missing_ok=True);raise ValueError('Original archive checksum mismatch')
 if target.open('rb').read(8)!=bytes.fromhex('526172211a070100'):
  target.unlink(missing_ok=True);raise ValueError('Not a RAR5 archive')
 return target
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output');a=p.parse_args()
 print('RESTORED:',restore(output=a.output))
