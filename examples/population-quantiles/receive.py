"""Independent final-JSON receiver; stdlib only, no producer/library imports."""
import argparse
import json
import math
import sys
from pathlib import Path


def compare(actual, expected, at='$'):
    if isinstance(expected, dict):
        assert isinstance(actual, dict) and actual.keys() == expected.keys(), at + ' object keys'
        for key in expected:
            compare(actual[key], expected[key], at + '.' + key)
    elif isinstance(expected, list):
        assert isinstance(actual, list) and len(actual) == len(expected), at + ' array size'
        for i, (value, truth) in enumerate(zip(actual, expected)):
            compare(value, truth, at + '[' + str(i) + ']')
    elif isinstance(expected, (int, float)) and not isinstance(expected, bool):
        assert isinstance(actual, (int, float)) and not isinstance(actual, bool), at + ' numeric type'
        assert math.isfinite(actual) and math.isfinite(expected), at + ' nonfinite JSON value'
        if isinstance(expected, int) or '.probabilities[' in at:
            assert actual == expected, (at, actual, expected)
        elif expected == 0.0 or abs(expected) < sys.float_info.min:
            assert actual == expected, (at, actual, expected)
        else:
            # Independent rational truth is rounded once, while the Double
            # implementation may round intermediate interpolation/moments.
            assert abs(actual - expected) <= 4 * math.ulp(expected), (at, actual, expected)
    else:
        assert type(actual) is type(expected) and actual == expected, (at, actual, expected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    parser.add_argument('--expected', type=Path, required=True)
    args = parser.parse_args()
    actual = json.loads(args.report.read_text(encoding='utf-8'))
    expected = json.loads(args.expected.read_text(encoding='utf-8'))
    compare(actual, expected)
    print(json.dumps({'status': 'passed', 'wholeReportMatches': True,
                      'numericPolicy': 'exact schema/counts/indices/probabilities/zero/subnormal; at most 4 ULP for other Double results',
                      'producerImports': False}))


if __name__ == '__main__':
    main()
