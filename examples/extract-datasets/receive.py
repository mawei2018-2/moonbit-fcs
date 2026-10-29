"""Original MIT standalone FCS/bundle receiver, independent of producer/fixtures.

Consumes full actual files, not assertions from a producer manifest. Also reads
the frozen source chain directly for baseline validation of original bytes.
"""
import argparse
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import struct

LAYOUT=['$BEGINDATA','$ENDDATA','$BEGINANALYSIS','$ENDANALYSIS']


def sha(data):return hashlib.sha256(data).hexdigest()


def pairs(segment):
    delimiter=segment[0];cells=[];cell=bytearray();index=1
    while index<len(segment):
        byte=segment[index]
        if byte==delimiter:
            if index+1<len(segment) and segment[index+1]==delimiter:
                cell.append(byte);index+=2;continue
            cells.append(cell.decode('utf-8'));cell.clear()
        else:cell.append(byte)
        index+=1
    assert not cell and len(cells)%2==0
    result=list(zip(cells[::2],cells[1::2]));assert len({key.upper() for key,value in result})==len(result)
    return {key.upper():value for key,value in result}


def decimal(text,source=False):
    text=text.strip(' ') if source else text
    assert text and all(char in '0123456789' for char in text)
    return int(text)


def frame(data,expected,offset=0,source=False,next_offset=0):
    version=expected['source_version'] if source else 'FCS3.1'
    assert data[offset:offset+10]==version.encode()+b'    '
    ts,te,ds,de,ast,ae=[int(data[offset+index:offset+index+8]) for index in [10,18,26,34,42,50]]
    assert ts==256 and data[offset+58:offset+ts]==b' '*(ts-58) and ts<=te<ds and de>=ds-1
    meta=pairs(data[offset+ts:offset+te+1])
    for key,value in zip(LAYOUT,[ds,de,ast,ae]):assert decimal(meta[key],source)==value
    actual={key:value for key,value in meta.items() if key not in LAYOUT}
    for key in ['$BEGINSTEXT','$ENDSTEXT']:assert decimal(actual[key],source)==0;actual[key]='0'
    assert decimal(actual['$NEXTDATA'],source)==next_offset
    actual['$NEXTDATA']=str(next_offset)
    wanted=dict(expected['metadataExceptLayoutOffsets'])
    if source:wanted['$ORIGINALITY']='Original';wanted['$NEXTDATA']=str(next_offset)
    assert actual==wanted,(actual,wanted)
    payload=data[offset+ds:offset+de+1]
    assert payload.hex()==expected['rawDataHex'],'DATA bytes differ from independent original expectation'
    if expected['analysis']:
        assert ast==de+1 and ae>=ast
        analysis=pairs(data[offset+ast:offset+ae+1]);end=offset+ae+1
    else:assert ast==ae==0;analysis={};end=offset+de+1
    assert analysis==expected['analysis']
    assert end<=len(data)
    if not source:assert offset==0 and end==len(data)
    count=int(meta['$PAR']);widths=[int(meta[f'$P{i}B'])//8 for i in range(1,count+1)]
    order='little' if meta['$BYTEORD']=='1,2,3,4' else 'big'
    flat=[];at=0
    if meta['$MODE']=='L':cell_widths=widths*int(meta['$TOT'])
    else:
        shape=[int(meta[f'$P{i}R']) for i in range(1,count+1)];assert len(set(widths))==1
        cell_widths=[widths[0]]*math.prod(shape)
    negative_zero=0;nan=0;positive_inf=0;negative_inf=0;finite=[]
    for width in cell_widths:
        cell=payload[at:at+width];assert len(cell)==width;at+=width
        if meta['$DATATYPE']=='I':value=int.from_bytes(cell,order)
        else:
            value=struct.unpack(('<' if order=='little' else '>')+'d',cell)[0]
            bits=int.from_bytes(cell,order)
            if math.isnan(value):nan+=1
            elif math.isinf(value):positive_inf+=int(value>0);negative_inf+=int(value<0)
            else:finite.append(Fraction(value));negative_zero+=int(value==0 and bits>>63==1)
        flat.append(value)
    assert at==len(payload)
    if meta['$MODE']!='L':
        assert sum(flat)==int(meta['$TOT'])
        stride=1;marginals=[]
        for bins in shape:
            marginals.append([sum(value for position,value in enumerate(flat) if position//stride%bins==bin_index) for bin_index in range(bins)])
            stride*=bins
        consumed={'frequencies':flat,'marginals':marginals,'total':sum(flat)}
    elif meta['$DATATYPE']=='I':consumed={'columnSums':[sum(flat[index::count]) for index in range(count)]}
    else:consumed={'finiteCount':len(finite),'finiteSum':str(sum(finite,Fraction(0))),'negativeZeroCount':negative_zero,
                   'nanCount':nan,'positiveInfinityCount':positive_inf,'negativeInfinityCount':negative_inf}
    assert consumed==expected['consumed'],(consumed,expected['consumed'])
    return {'version':version,'DATABytes':len(payload),'decodedCells':len(flat),'analysis':analysis,'consumed':consumed,'frameEnd':end}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path',type=Path);parser.add_argument('--expected',required=True,type=Path)
    parser.add_argument('--dataset-expected',action='store_true');parser.add_argument('--source-chain',action='store_true')
    parser.add_argument('--source-file')
    args=parser.parse_args();expected=json.loads(args.expected.read_text(encoding='utf-8'))
    if args.dataset_expected:
        data=args.path.read_bytes();result=frame(data,expected)
        print(json.dumps({'file':str(args.path),'bytes':len(data),'SHA256':sha(data),**result},ensure_ascii=False));return
    if args.source_chain:
        data=args.path.read_bytes();assert sha(data)==expected['source_sha256'];results=[]
        rows=expected['datasets']
        for index,row in enumerate(rows):
            offset=row['source_offset'];next_offset=rows[index+1]['source_offset']-offset if index+1<len(rows) else 0
            result=frame(data,row,offset,True,next_offset);results.append(result)
            if next_offset:assert data[result['frameEnd']:offset+next_offset]==b'\x00'*(offset+next_offset-result['frameEnd'])
        assert results[-1]['frameEnd']==len(data)
        print(json.dumps({'sourceSHA256':sha(data),'datasets':len(results),'decodedCells':sum(item['decodedCells'] for item in results),'frames':results},ensure_ascii=False));return
    manifest_path=args.path/'manifest.json';manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    assert set(manifest)=={'schema_version','source_file','source_sha256','datasets'} and manifest['schema_version']==1
    if args.source_file is not None:assert manifest['source_file']==args.source_file
    assert manifest['source_sha256']==expected['source_sha256'] and len(manifest['datasets'])==len(expected['datasets'])
    assert {path.name for path in args.path.iterdir()}=={'manifest.json'}|{f'dataset-{index:06d}.fcs' for index in range(len(expected['datasets']))}
    received=[]
    keys=['dataset','source_offset','source_version','source_mode','source_events','source_warnings']
    for index,(item,row) in enumerate(zip(manifest['datasets'],expected['datasets'])):
        assert set(item)==set(keys)|{'file','bytes','sha256'}
        assert {key:item[key] for key in keys}=={key:row[key] for key in keys}
        assert item['file']==f'dataset-{index:06d}.fcs'
        data=(args.path/item['file']).read_bytes();assert len(data)==item['bytes'] and sha(data)==item['sha256']
        result=frame(data,row);received.append({'file':item['file'],'bytes':len(data),'SHA256':sha(data),**result})
    print(json.dumps({'datasets':len(received),'decodedCells':sum(item['decodedCells'] for item in received),'manifestSHA256':sha(manifest_path.read_bytes()),'files':received},ensure_ascii=False))


if __name__=='__main__':main()
