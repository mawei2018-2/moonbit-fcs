"""Original MIT independent complete FCS output receiver.

Only standard-library HEADER/TEXT/DATA decoding; no product or fixture import.
Every metadata key/value and raw DATA byte (or every fixed ASCII field) is
checked, followed by positional stain/value or histogram marginal consumption.
"""
import argparse
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import struct


def text_pairs(segment):
    delimiter=segment[0];fields=[];cell=bytearray();index=1
    while index<len(segment):
        value=segment[index]
        if value==delimiter:
            if index+1<len(segment) and segment[index+1]==delimiter:
                cell.append(value);index+=2;continue
            fields.append(cell.decode('utf-8'));cell.clear()
        else:cell.append(value)
        index+=1
    assert not cell and len(fields)%2==0
    pairs=list(zip(fields[::2],fields[1::2]))
    assert len({key.upper() for key,value in pairs})==len(pairs)
    return {key.upper():value for key,value in pairs}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('fcs',type=Path);parser.add_argument('--expected',type=Path,required=True)
    args=parser.parse_args();expected=json.loads(args.expected.read_text(encoding='utf-8'));data=args.fcs.read_bytes()
    assert data[:10]==b'FCS3.1    '
    ts,te,ds,de,ast,ae=[int(data[index:index+8]) for index in [10,18,26,34,42,50]]
    assert ts==256 and data[58:ts]==b' '*(ts-58) and ts<=te<ds<=de and de+1==len(data)
    assert ast==ae==0
    meta=text_pairs(data[ts:te+1]);assert int(meta['$BEGINDATA'])==ds and int(meta['$ENDDATA'])==de
    actual={key:value for key,value in meta.items() if key not in ['$BEGINDATA','$ENDDATA']}
    # Segment offsets are FCS decimal numbers. The frozen expected zero keeps
    # its value when a canonical writer uses zero-padded decimal spelling.
    for key in ['$BEGINSTEXT','$ENDSTEXT','$BEGINANALYSIS','$ENDANALYSIS']:
        value=actual[key]
        assert value and all(char in '0123456789' for char in value) and int(value)==0
        actual[key]='0'
    assert actual==expected['metadataExceptDataOffsets'],(actual,expected['metadataExceptDataOffsets'])
    payload=data[ds:de+1];assert len(payload)==expected['expectedDataBytes']
    if expected['rawDataHex'] is not None:assert payload.hex()==expected['rawDataHex'],'complete raw DATA differs'
    count=int(meta['$PAR']);widths=[int(meta[f'$P{i}B']) for i in range(1,count+1)]
    order='little' if meta['$BYTEORD']=='1,2,3,4' else 'big'
    widths=widths if meta['$DATATYPE']=='A' else [width//8 for width in widths]
    if meta['$MODE']=='L':cell_widths=widths*int(meta['$TOT'])
    else:
        shape=[int(meta[f'$P{i}R']) for i in range(1,count+1)]
        if meta['$MODE']=='C':
            assert len(set(widths))==1
            cell_widths=[widths[0]]*math.prod(shape)
        else:cell_widths=[width for width,bins in zip(widths,shape) for _ in range(bins)]
    flat=[];at=0
    for width in cell_widths:
        cell=payload[at:at+width];assert len(cell)==width;at+=width
        if meta['$DATATYPE']=='I':value=int.from_bytes(cell,order)
        elif meta['$DATATYPE']=='A':
            assert all(byte in b' 0123456789+-' for byte in cell)
            value=int(cell.strip().decode('ascii'))
        else:value=struct.unpack(('<' if order=='little' else '>')+('f' if meta['$DATATYPE']=='F' else 'd'),cell)[0]
        flat.append(value)
    assert at==len(payload)
    values=[flat[i:i+count] for i in range(0,len(flat),count)] if meta['$MODE']=='L' else flat
    assert values==expected['values'],(values,expected['values'])
    consumed={}
    if meta['$MODE']=='L':
        for index in range(count):
            stain=meta[f'$P{index+1}S'];assert stain not in consumed
            consumed[stain]=str(sum((Fraction(row[index]) for row in values),Fraction(0)))
    else:
        shape=[int(meta[f'$P{i}R']) for i in range(1,count+1)]
        total=int(meta['$TOT'])
        if meta['$MODE']=='C':
            assert len(flat)==math.prod(shape) and sum(flat)==total
            stride=1
            for axis,bins in enumerate(shape):
                marginal=[sum(value for position,value in enumerate(flat) if position//stride%bins==bin_index) for bin_index in range(bins)]
                consumed[meta[f'$P{axis+1}S']]=marginal;stride*=bins
        else:
            assert len(flat)==sum(shape);start=0
            for axis,bins in enumerate(shape):
                marginal=flat[start:start+bins];assert sum(marginal)==total
                consumed[meta[f'$P{axis+1}S']]=marginal;start+=bins
    print(json.dumps({'bytes':len(data),'SHA256':hashlib.sha256(data).hexdigest(),'mode':meta['$MODE'],
                      'datatype':meta['$DATATYPE'],'channels':count,'values':values,'consumedByStain':consumed},ensure_ascii=False))


if __name__=='__main__':main()
