"""Original MIT CSV-only cohort receiver. No FCS or producer import.

Consumes the delivered file, checks every field against frozen expectations,
then pivots all sample/population counts and ranks samples by band frequency.
This self-authored real receiver does not establish external adoption.
"""
import argparse
import csv
from fractions import Fraction
import hashlib
import io
import json
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv',type=Path)
    parser.add_argument('--expected',required=True,type=Path)
    args=parser.parse_args()
    expected=json.loads(args.expected.read_text(encoding='utf-8'))
    data=args.csv.read_bytes()
    digest=hashlib.sha256(data).hexdigest()
    assert digest==expected['bytesSHA256'],'complete CSV bytes differ'
    reader=csv.reader(io.StringIO(data.decode('utf-8'),newline=''))
    header=next(reader)
    assert header==expected['header'],header
    rows=list(reader)
    assert rows==expected['rows'],'complete sample/source/population association differs'
    pivot={};band=[]
    for row in rows:
        item=dict(zip(header,row))
        sample=item['sample'];population=item['population']
        assert population not in pivot.setdefault(sample,{})
        count,parent,total=[int(item[key]) for key in ['count','parent_count','total_count']]
        assert 0<=count<=parent<=total
        pivot[sample][population]=count
        for field,denominator in [('parent_fraction',parent),('total_fraction',total)]:
            value=item[field]
            if denominator==0:
                assert value==''
            else:
                assert value!='' and abs(Fraction(value)-Fraction(count,denominator))<=Fraction(1,10**15)
        assert isinstance(json.loads(item['read_warnings']),list)
        assert len(item['source_sha256'])==64
        if population=='band':band.append((sample,Fraction(item['total_fraction'] or 0)))
    rank=[sample for sample,fraction in sorted(band,key=lambda item:-item[1])]
    assert pivot==expected['pivotCounts']
    assert len(pivot)==expected['sampleCount'] and rank==expected['rankByBand']
    print(json.dumps({'rows':len(rows),'samples':len(pivot),'pivotCounts':pivot,
                      'rankByBand':rank,'SHA256':digest},ensure_ascii=False))


if __name__=='__main__':main()
