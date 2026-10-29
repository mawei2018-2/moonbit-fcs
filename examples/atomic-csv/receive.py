"""Independent CSV-only file receiver, original MIT. No FCS/bridge import.

An optional expectation file describes explicit fields/rows or the I16 index
rule. This example is a self-authored consumer, not evidence of external use.
"""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv', type=Path)
    parser.add_argument('--expected', type=Path)
    args = parser.parse_args()
    expectation = json.loads(args.expected.read_text(encoding='utf-8')) if args.expected else {}
    try:
        data = args.csv.read_bytes()
    except FileNotFoundError:
        assert expectation.get('state') == 'absent', 'expected a complete received file'
        print(json.dumps({'state': 'absent'}))
        return
    assert expectation.get('state') != 'absent', 'final filename became visible before publication'
    digest = hashlib.sha256(data).hexdigest()
    if 'bytesSHA256' in expectation:
        assert digest == expectation['bytesSHA256'], 'received bytes differ from independent expectation'
    if expectation.get('state') == 'bytes':
        print(json.dumps({'state':'preserved','bytes':len(data),'SHA256':digest}))
        return
    reader = csv.reader(io.StringIO(data.decode('utf-8'), newline=''))
    header = next(reader)
    if 'header' in expectation:
        assert header == expectation['header'], (header, expectation['header'])
    count = 0
    for row in reader:
        if 'rows' in expectation:
            assert count < len(expectation['rows']) and row == expectation['rows'][count], (count, row)
        if 'rule' in expectation:
            assert row == [str(count), str(count % 65536)], (count, row)
        count += 1
    if 'rows' in expectation:
        assert count == len(expectation['rows'])
    if 'rule' in expectation:
        assert expectation['rule'] == 'source_index_i_value_i_mod_65536'
        assert count == 100001
    print(json.dumps({'state': 'received', 'header': header, 'rows': count, 'bytes': len(data), 'SHA256': digest}))


if __name__ == '__main__':
    main()
