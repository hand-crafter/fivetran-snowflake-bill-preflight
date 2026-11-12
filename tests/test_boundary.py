import csv
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import tokenize
import unittest

ROOT = Path(__file__).resolve().parents[1]

class PublicBoundaryTests(unittest.TestCase):
    def test_no_paid_logic_or_sections(self):
        source = (ROOT/'preflight.py').read_text()
        forbidden = ('candidates', 'scenario', 'spike')
        identifiers = [t.string for t in tokenize.generate_tokens(io.StringIO(source).readline)
                       if t.type == tokenize.NAME and any(x in t.string.lower() for x in forbidden)]
        self.assertEqual(identifiers, [], 'paid code identifiers remain')
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            out = Path(temp)/'report'
            result = subprocess.run([sys.executable, str(ROOT/'preflight.py'), str(ROOT/'fixtures'),
                                     '--output', str(out)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(out.with_suffix('.json').read_text())
            self.assertFalse(any(x in k.lower() for k in report for x in forbidden))
            with out.with_suffix('.csv').open() as f:
                self.assertFalse(any(x in row['section'].lower() for row in csv.DictReader(f) for x in forbidden))
            document = out.with_suffix('.html').read_text().lower()
            import re
            headings = re.findall(r'<h[12][^>]*>(.*?)</h[12]>', document)
            self.assertFalse(any(x in h for h in headings for x in forbidden))
