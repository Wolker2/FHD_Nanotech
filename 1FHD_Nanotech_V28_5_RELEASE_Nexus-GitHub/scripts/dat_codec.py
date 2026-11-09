"""Space Rangers HD DAT (BlockPar + CacheData) lossless JSON codec.

Format algorithm follows the rangers-utils / Prolog_D-compatible serializer.
Carries sorted entry order, metadata, encryption seed and resource-DAT wrapper.
"""
import struct, zlib, json
from pathlib import Path
KEYS={'blockpar':bytes.fromhex('89 c6 e8 b1'),'cachedata':bytes.fromhex('37 3f 8f ea')}
OUTER_KEYS=(0x7db6c99d,0xc83fcbf3)
def outer_header(data):
 a,b=OUTER_KEYS
 checked=struct.pack('<I',zlib.crc32(data)^a)+data
 return struct.pack('<II',len(data)^a^b,zlib.crc32(checked)^b)
def cipher(data, seed):
 seed=int(seed)&0xffffffff
 if seed>=0x80000000:seed-=0x100000000
 out=bytearray(data)
 for i in range(len(out)):
  hi,lo=divmod(seed,0x1f31d)
  seed=lo*0x41a7-hi*0xb14
  if seed<1:seed+=0x7fffffff
  out[i]^=(seed-1)&255
 return bytes(out)
class Reader:
 def __init__(self,data):self.data=data;self.p=0
 def take(self,n):
  if self.p+n>len(self.data):raise ValueError('DAT EOF')
  v=self.data[self.p:self.p+n];self.p+=n;return v
 def u8(self):return self.take(1)[0]
 def u32(self):return struct.unpack('<I',self.take(4))[0]
 def wide(self):
  st=self.p
  while self.p+2<=len(self.data):
   if self.take(2)==b'\0\0':return self.data[st:self.p-2].decode('utf-16le')
  raise ValueError('Missing UTF16 terminator')
 def block(self,fmt,depth=0):
  if depth>100:raise ValueError('Excessive nested blocks')
  sorted_flag=bool(self.u8()) if fmt=='blockpar' else None
  n=self.u32();out=[]
  if n>1000000:raise ValueError('Too many fields')
  for _ in range(n):
   sort_meta=[self.u32(),self.u32()] if sorted_flag else None
   kind=self.u8();name=self.wide()
   if kind==1: v={'kind':'parameter','name':name,'value':self.wide()}
   elif kind==2:v={'kind':'block','name':name,'value':self.block(fmt,depth+1)}
   else:raise ValueError('Invalid block record '+str(kind))
   if sort_meta is not None:v['sort_meta']=sort_meta
   out.append(v)
  b={'entries':out}
  if fmt=='blockpar':b['sorted']=sorted_flag
  return b
def decode(data,fmt):
 wrapped=fmt=='cachedata' and len(data)>24 and data[:8]==outer_header(data[8:])
 if wrapped:data=data[8:]
 key=KEYS[fmt]
 if len(data)<16:raise ValueError('Short DAT')
 crc=struct.unpack_from('<I',data)[0]
 seed=int.from_bytes(bytes(a^b for a,b in zip(data[4:8],key)),'little',signed=True)
 zipped=cipher(data[8:],seed)
 if zlib.crc32(zipped)!=crc:raise ValueError('DAT CRC mismatch')
 if zipped[:4]!=b'ZL01':raise ValueError('Not ZL01 DAT')
 expected=struct.unpack_from('<I',zipped,4)[0];raw=zlib.decompress(zipped[8:])
 if len(raw)!=expected:raise ValueError('DAT uncompressed size mismatch')
 r=Reader(raw);root=r.block(fmt)
 if r.p!=len(raw):raise ValueError('Trailing bytes')
 p={'format':fmt,'seed':seed,'root':root}
 if wrapped:p['outer_checksum']='resource-dat-v1'
 return p
def wide(out,s):out.extend(s.encode('utf-16le'));out.extend(b'\0\0')
def block(out,b,fmt):
 sorted_flag=bool(b.get('sorted')) if fmt=='blockpar' else False
 if fmt=='blockpar':out.append(int(sorted_flag))
 rows=b['entries'];out.extend(struct.pack('<I',len(rows)))
 for i,x in enumerate(rows):
  if sorted_flag:
   if 'sort_meta' in x:n,count=x['sort_meta']
   else:
    n=0;count=0
    while i-n>0 and rows[i-n-1]['name']==x['name']:n+=1
    if n==0:count=sum(y['name']==x['name'] for y in rows)
   out.extend(struct.pack('<II',n,count))
  out.append(1 if x['kind']=='parameter' else 2);wide(out,x['name'])
  if x['kind']=='parameter':wide(out,x['value'])
  else:block(out,x['value'],fmt)
def encode(p):
 fmt=p['format'];seed=p['seed'];raw=bytearray();block(raw,p['root'],fmt)
 zipped=b'ZL01'+struct.pack('<I',len(raw))+zlib.compress(raw,9)
 key=KEYS[fmt];sb=(int(seed)&0xffffffff).to_bytes(4,'little')
 payload=struct.pack('<I',zlib.crc32(zipped))+bytes(a^b for a,b in zip(sb,key))+cipher(zipped,seed)
 if p.get('outer_checksum')=='resource-dat-v1':payload=outer_header(payload)+payload
 return payload
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['decode','encode','verify']);p.add_argument('input');p.add_argument('output');p.add_argument('--format',choices=KEYS)
 a=p.parse_args();src=Path(a.input);dst=Path(a.output)
 if a.mode=='decode':
  data=decode(src.read_bytes(),a.format);dst.parent.mkdir(parents=True,exist_ok=True);dst.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 else:
  dat=encode(json.loads(src.read_text('utf-8')))
  if a.mode=='verify':assert dst.read_bytes()==dat,'Not byte exact'
  else:dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(dat)
