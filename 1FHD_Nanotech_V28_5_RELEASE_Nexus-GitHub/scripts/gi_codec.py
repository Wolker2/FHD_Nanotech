"""Lossless editable GI type 0/1/2 JSON <-> original sprite format.
Reimplementation of the game's GI RLE channel encoding for NanoTech assets.
Gai animations and Hai atlases are preserved separately (not decoded here).
"""
import struct

def decode(data):
 if len(data)<64 or data[:4]!=b'gi\0\0':raise ValueError('Invalid GI magic')
 h=struct.unpack_from('<15I',data,4);kind,count=h[9:11]
 if (kind,count) not in [(0,1),(1,1),(2,3)]:raise ValueError('Unsupported GI type '+str((kind,count)))
 result={'format':'srhd-gi012-json-v1','type':kind,'version':h[0],
         'bounds':list(h[1:5]),'masks':list(h[5:9]),'reserved':list(h[11:15]),'layers':[]}
 consumed=64+32*count
 for index in range(count):
  offset,size,*descriptor=struct.unpack_from('<8I',data,64+32*index)
  layer={'bounds':descriptor[:4],'reserved':descriptor[4:],'empty_offset':offset if not size else 0}
  if not size:layer['commands']=[];result['layers'].append(layer);continue
  if offset!=consumed:raise ValueError('Noncontiguous GI layers')
  payload=data[offset:offset+size]
  if len(payload)!=size:raise ValueError('Truncated GI')
  if kind==0:
   if h[5:9]==(0xf800,0x7e0,0x1f,0):fmt='H';layer['pixel_format']='rgb565'
   elif h[5:9]==(0xff0000,0xff00,0xff,0xff000000):fmt='I';layer['pixel_format']='argb8888'
   else:raise ValueError('Unsupported raw channel masks')
   layer['pixels']=[v[0] for v in struct.iter_unpack('<'+fmt,payload)]
   width,height=descriptor[2]-descriptor[0],descriptor[3]-descriptor[1]
   if len(layer['pixels'])!=width*height:raise ValueError('Pixels vs area mismatch')
  else:
   encoded,width,height,reserved=struct.unpack_from('<4I',payload)
   if encoded!=size-16:raise ValueError('Invalid GI encoded length')
   layer.update(width=width,height=height,rle_reserved=reserved,
                pixel_format='transparency6' if kind==2 and index==2 else 'rgb565',commands=[])
   pos=16;fmt='B' if kind==2 and index==2 else 'H';stride=struct.calcsize(fmt)
   while pos<len(payload):
    command=payload[pos];pos+=1
    if command in [0,128]:layer['commands'].append({'end_row':command})
    elif command<128:layer['commands'].append({'skip':command})
    else:
     count_pixels=command-128
     vals=list(struct.unpack_from('<'+fmt*count_pixels,payload,pos));pos+=stride*count_pixels
     layer['commands'].append({'pixels':vals})
   if pos!=len(payload):raise ValueError('Unparsed GI RLE')
  consumed+=size;result['layers'].append(layer)
 if consumed!=len(data):raise ValueError('Trailing bytes in GI')
 return result

def encode(source):
 if source['format']!='srhd-gi012-json-v1':raise ValueError('Bad GI source format')
 kind=source['type'];layers=source['layers']
 if (kind,len(layers)) not in [(0,1),(1,1),(2,3)]:raise ValueError('Unsupported GI type')
 header=struct.pack('<4s15I',b'gi\0\0',source['version'],*source['bounds'],*source['masks'],kind,len(layers),*source['reserved'])
 offset=64+32*len(layers);descriptors=[];payloads=[]
 for index,layer in enumerate(layers):
  if kind==0 and 'pixels' in layer:
   fmt='H' if layer['pixel_format']=='rgb565' else 'I';bounds=layer['bounds']
   if len(layer['pixels'])!=(bounds[2]-bounds[0])*(bounds[3]-bounds[1]):raise ValueError('Invalid raw GI area')
   payload=struct.pack('<'+fmt*len(layer['pixels']),*layer['pixels'])
  else:
   body=bytearray();fmt='B' if kind==2 and index==2 else 'H'
   for command in layer['commands']:
    if 'end_row' in command:
     if command['end_row'] not in [0,128]:raise ValueError('Invalid end_row')
     body.append(command['end_row'])
    elif 'skip' in command:
     if not 1<=command['skip']<=127:raise ValueError('Invalid skip')
     body.append(command['skip'])
    elif 'pixels' in command:
     pixels=command['pixels']
     if not 1<=len(pixels)<=127:raise ValueError('Invalid span')
     if fmt=='B' and not all(0<=v<=63 for v in pixels):raise ValueError('Transparency out of range')
     body.append(128+len(pixels));body.extend(struct.pack('<'+fmt*len(pixels),*pixels))
    else:raise ValueError('Unknown GI command')
   payload=struct.pack('<4I',len(body),layer['width'],layer['height'],layer['rle_reserved'])+body if body else b''
  descriptors.append(struct.pack('<8I',offset if payload else layer['empty_offset'],len(payload),*layer['bounds'],*layer['reserved']))
  payloads.append(payload);offset+=len(payload)
 return header+b''.join(descriptors)+b''.join(payloads)

if __name__=='__main__':
 import argparse,json
 from pathlib import Path
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['decode','encode','verify']);p.add_argument('input');p.add_argument('output');a=p.parse_args()
 if a.mode=='decode':
  src=decode(Path(a.input).read_bytes());Path(a.output).parent.mkdir(exist_ok=True,parents=True)
  Path(a.output).write_text(json.dumps(src,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
 else:
  data=encode(json.loads(Path(a.input).read_text('utf-8')))
  if a.mode=='verify':assert Path(a.output).read_bytes()==data
  else:Path(a.output).parent.mkdir(exist_ok=True,parents=True);Path(a.output).write_bytes(data)
