#!/usr/bin/env python3
"""A delivery requires executed tests and no failures, errors or skipped cases."""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def check_results(path):
    cases = list(ET.parse(path).iter("testcase"))
    if not cases:
        raise ValueError("The test report contains no executed cases")
    invalid = [
        case.get("name", "unknown")
        for case in cases
        if any(case.find(tag) is not None for tag in ("failure", "error", "skipped"))
    ]
    if invalid:
        raise ValueError(f"Failed or skipped tests: {', '.join(invalid)}")
    return len(cases)


if __name__ == "__main__":
    try:
        count = check_results(Path(sys.argv[1]))
        print(f"Verified {count} passing tests with no skipped cases.")
    except (IndexError, OSError, ET.ParseError, ValueError) as error:
        print(f"Delivery check failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
