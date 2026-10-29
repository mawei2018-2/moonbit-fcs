"""Independent stdlib-only consumer of complete final compensation JSON/CSV/FCS."""
import argparse
import csv
import json
import math
from pathlib import Path
import struct


def text_pairs(raw):
    assert raw
    delimiter = raw[0]
    fields, value, at = [], bytearray(), 1
    while at < len(raw):
        if raw[at] != delimiter:
            value.append(raw[at]); at += 1
        elif at+1 < len(raw) and raw[at+1] == delimiter:
            value.append(delimiter); at += 2
        else:
            fields.append(value.decode('utf-8')); value = bytearray(); at += 1
    assert not value and len(fields) % 2 == 0
    result = dict(zip(fields[::2], fields[1::2]))
    assert len(result)*2 == len(fields)
    return result


def fcs(path):
    raw = path.read_bytes()
    assert raw[:10] == b'FCS3.1    ' and len(raw) >= 58
    ts, te, ds, de, ab, ae = [int(raw[at:at+8]) for at in range(10,58,8)]
    assert 58 <= ts <= te < ds
    metadata = text_pairs(raw[ts:te+1])
    assert (ds, de) == (int(metadata['$BEGINDATA']), int(metadata['$ENDDATA']))
    assert metadata['$DATATYPE'] == 'D' and metadata['$MODE'] == 'L' and metadata['$BYTEORD'] == '1,2,3,4'
    events, channels = int(metadata['$TOT']), int(metadata['$PAR'])
    assert all(metadata[f'$P{i}B'] == '64' for i in range(1,channels+1))
    assert de == ds + events*channels*8 - 1 and len(raw) == de+1
    assert (ab, ae) == (int(metadata['$BEGINANALYSIS']), int(metadata['$ENDANALYSIS'])) == (0,0)
    data = raw[ds:de+1]
    values, bit_patterns = [], []
    for event in range(events):
        row, row_bits = [], []
        for channel in range(channels):
            piece = data[(event*channels+channel)*8:(event*channels+channel+1)*8]
            value = struct.unpack('<d',piece)[0]
            row.append('NaN' if math.isnan(value) else 'Infinity' if value == math.inf else '-Infinity' if value == -math.inf else value)
            row_bits.append('NaN' if math.isnan(value) else str(int.from_bytes(piece,'little')))
        values.append(row); bit_patterns.append(row_bits)
    layout = {'$BEGINDATA','$ENDDATA','$BEGINANALYSIS','$ENDANALYSIS'}
    return {'version':'FCS3.1','metadataExceptLayout':{key:value for key,value in metadata.items() if key not in layout},
            'analysis':{},'rawDataHex':data.hex(),'values':values,'bits':bit_patterns}


def compare(actual, expected, location='$'):
    if isinstance(expected,dict):
        assert isinstance(actual,dict) and actual.keys() == expected.keys(), location+' keys'
        for key in expected: compare(actual[key],expected[key],location+'.'+key)
    elif isinstance(expected,list):
        assert isinstance(actual,list) and len(actual)==len(expected), location+' length'
        for i,(value,truth) in enumerate(zip(actual,expected)): compare(value,truth,location+'['+str(i)+']')
    elif isinstance(expected,(int,float)) and not isinstance(expected,bool):
        assert isinstance(actual,(int,float)) and not isinstance(actual,bool) and actual==expected,(location,actual,expected)
    else:
        assert type(actual) is type(expected) and actual==expected,(location,actual,expected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file',type=Path)
    parser.add_argument('--expected',type=Path,required=True)
    parser.add_argument('--kind',choices=['json','csv','fcs'],required=True)
    args=parser.parse_args()
    if args.kind=='fcs': actual=fcs(args.file)
    elif args.kind=='csv':
        with args.file.open(encoding='utf-8',newline='') as stream: actual=list(csv.reader(stream))
    else: actual=json.loads(args.file.read_text('utf-8'))
    compare(actual,json.loads(args.expected.read_text('utf-8')))
    print(json.dumps({'status':'passed','wholeFileCompared':True,'producerImports':False,'kind':args.kind}))


if __name__=='__main__': main()
