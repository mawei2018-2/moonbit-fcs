"""Original MIT CSV-only membership receiver; no FCS or producer import.

Checks complete independently expected rows, then computes counts/intersection
and sorts the received records while retaining their source-index association.
Self-authored consumption is not evidence of external adoption.
"""
import argparse
import csv
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv', type=Path)
    parser.add_argument('--expected', required=True, type=Path)
    args = parser.parse_args()
    expected = json.loads(args.expected.read_text(encoding='utf-8'))
    data = args.csv.read_bytes()
    assert hashlib.sha256(data).hexdigest() == expected['bytesSHA256'], 'complete CSV bytes differ'
    reader = csv.reader(io.StringIO(data.decode('utf-8'), newline=''))
    header = next(reader)
    assert header == expected['header'], (header, expected['header'])
    counts = {name:0 for name in expected.get('counts',{})}
    kept = []
    for index,row in enumerate(reader):
        if expected.get('rule'):
            x,y = index%13,index%7
            a = 2 <= x < 9
            b = a and 1 <= y < 4
            c = 5 <= y < 7
            assert row == list(map(str,[index,y,x,int(a),int(b),int(c)])), (index,row)
        else:
            assert index < len(expected['rows']) and row == expected['rows'][index], (index,row)
            kept.append(row)
        for label in counts:
            value = row[header.index(label)]
            assert value in ['0','1']
            counts[label] += int(value)
    total = index+1 if 'index' in locals() else 0
    assert total == expected.get('events',len(expected.get('rows',[])))
    assert counts == expected.get('counts',{})
    intersection = None
    if 'intersection' in expected:
        rule = expected['intersection']
        intersection = [int(row[header.index('source_event_index')]) for row in kept
                        if all(row[header.index(name)]=='1' for name in rule['columns'])]
        assert intersection == rule['source_indices']
    sorted_indices = None
    if 'sort' in expected:
        order = expected['sort']
        # Operate on the received CSV only, including decimal scientific values.
        records = sorted(kept,key=lambda row:Decimal(row[header.index(order['column'])]),reverse=True)
        sorted_indices = [int(row[header.index('source_event_index')]) for row in records]
        assert sorted_indices == order['source_indices']
        lookup = {row[header.index('source_event_index')]:row for row in expected['rows']}
        assert all(row == lookup[row[header.index('source_event_index')]] for row in records)
    print(json.dumps({'events':total,'counts':counts,'intersection_source_indices':intersection,
                      'sorted_source_indices':sorted_indices,'SHA256':hashlib.sha256(data).hexdigest()}))


if __name__ == '__main__':
    main()
