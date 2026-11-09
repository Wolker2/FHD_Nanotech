#!/usr/bin/env python3
"""Build installable ZIP for Nanotech V28.5 RELEASE + Nanogenesis.

Requires original archive fragments from install/parts and editable source JSON.
On Linux uses system libarchive.so.13. Else uses 7z/7zz executable only
for RAR extraction in a BUILD directory, never as a game launcher.
"""
from pathlib import Path
import sys,hashlib,zipfile, tempfile, json, shutil,subprocess,ctypes as C
from restore_original import restore,ROOT
from dat_codec import encode as encode_dat
from gi_codec import encode as encode_gi

def unpack_rar(original,target):
 try:
  lib=C.CDLL('libarchive.so.13')
 except OSError:
  tool=shutil.which('7z') or shutil.which('7zz') or shutil.which('bsdtar')
  if tool is None:raise RuntimeError('RAR5 extraction needs libarchive (Linux) or 7-Zip (Windows)')
  args=[tool,'x','-y',f'-o{target}',str(original)] if '7z' in Path(tool).name else [tool,'-x','-f',str(original),'-C',str(target)]
  subprocess.run(args,check=True,stdout=subprocess.DEVNULL);return
 def wrap(name,result,args):
  fun=getattr(lib,name);fun.restype=result;fun.argtypes=args;return fun
 ptr=C.c_void_p;new=wrap('archive_read_new',ptr,[])
 wrap('archive_read_support_format_all',C.c_int,[ptr]);wrap('archive_read_support_filter_all',C.c_int,[ptr])
 openf=wrap('archive_read_open_filename',C.c_int,[ptr,C.c_char_p,C.c_size_t]);nex=wrap('archive_read_next_header',C.c_int,[ptr,C.POINTER(ptr)])
 pathname=wrap('archive_entry_pathname',C.c_char_p,[ptr]);filetype=wrap('archive_entry_filetype',C.c_uint,[ptr]);read=wrap('archive_read_data',C.c_ssize_t,[ptr,ptr,C.c_size_t]);err=wrap('archive_error_string',C.c_char_p,[ptr]);free=wrap('archive_read_free',C.c_int,[ptr])
 a=new();lib.archive_read_support_format_all(a);lib.archive_read_support_filter_all(a)
 if openf(a,str(original).encode(),10240):raise RuntimeError('Open RAR: '+str(err(a)))
 item=ptr();buf=C.create_string_buffer(524288)
 try:
  while True:
   status=nex(a,C.byref(item))
   if status==1:break
   if status<0:raise RuntimeError('RAR: '+str(err(a)))
   name=pathname(item).decode('utf-8');rel=Path(name)
   if rel.is_absolute() or '..' in rel.parts:raise RuntimeError('Unsafe archive path')
   if name.endswith('/') or filetype(item)==0o040000:continue
   dst=target/rel;dst.parent.mkdir(parents=True,exist_ok=True)
   with dst.open('wb') as out:
    while True:
     n=read(a,buf,len(buf))
     if n==0:break
     if n<0:raise RuntimeError('RAR read failed: '+name)
     out.write(buf.raw[:n])
 finally:free(a)

def build(verify=False,output=None):
 source=ROOT/'source';manifest=json.loads((ROOT/'runtime-manifest.json').read_text('utf-8'))
 src_zip=ROOT/'source'/'graphics_gi_JSON.zip'
 # The source ZIP is stored as smaller Git blobs; restore into the build temp
 # directory when a standalone unsplit copy is not present.
 if not src_zip.exists():
  info=json.loads((ROOT/'source'/'graphics_gi_parts.json').read_text('utf-8'))
  src_zip=ROOT/'dist'/'graphics_gi_JSON_restored.zip'
  src_zip.parent.mkdir(parents=True,exist_ok=True)
  h=hashlib.sha256();size=0
  with src_zip.open('wb') as dest:
   for record in info['parts']:
    f=ROOT/'source'/'graphics_gi_parts'/record['file']
    blob=f.read_bytes()
    if len(blob)!=record['size'] or hashlib.sha256(blob).hexdigest()!=record['sha256']:
     raise RuntimeError('Corrupt graphics source fragment: '+str(f))
    h.update(blob);size+=len(blob);dest.write(blob)
  if size!=info['size'] or h.hexdigest()!=info['sha256']:
   src_zip.unlink(missing_ok=True)
   raise RuntimeError('Graphics source archive checksum mismatch')
 target=Path(output) if output else ROOT/'dist/FHD_Nanotech_V28_5_RELEASE_INSTALL.zip'
 target.parent.mkdir(exist_ok=True,parents=True)
 original=restore()
 with tempfile.TemporaryDirectory(prefix='fhd-nano-build-') as tmp:
  game=Path(tmp);unpack_rar(original,game)
  with zipfile.ZipFile(src_zip) as sprites:
   sprite_names=set(sprites.namelist())
   results={};checks=0
   for record in manifest:
    rel=record['path'];filename=Path(*Path(rel).parts[2:]);orig=(game/rel).read_bytes();data=orig
    if filename.suffix=='.dat':
     p=source/(str(filename)+'.json');data=encode_dat(json.loads(p.read_text('utf-8')));checks+=1
    if filename.suffix=='.gi':
     k=filename.as_posix()+'.json'
     if k not in sprite_names:raise FileNotFoundError('Missing GI JSON for '+k)
     data=encode_gi(json.loads(sprites.read(k)));checks+=1
    if verify and hashlib.sha256(data).hexdigest()!=record['sha256']:
     raise RuntimeError('Original bytes differ: '+rel)
    results[rel]=data
  if len(results)!=526:raise RuntimeError('Missing runtime files')
  with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9,allowZip64=True) as out:
   for name,data in sorted(results.items()):
    z=zipfile.ZipInfo(name,(2026,1,1,0,0,0));z.external_attr=0o644<<16
    out.writestr(z,data,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
  return {'runtime_files':len(results),'exact_byte_checks':len(results) if verify else 0,'editable_dat_gi':checks,'zip':str(target),'size':target.stat().st_size}
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--verify-original',action='store_true');p.add_argument('--output');a=p.parse_args()
 print(json.dumps(build(verify=a.verify_original,output=a.output),ensure_ascii=False,indent=2))
