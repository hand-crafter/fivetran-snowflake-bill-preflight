import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from generate_fixtures import generate, write_csv

ROOT = Path(__file__).resolve().parents[1]


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        generate(self.folder)
        # Ready exports isolate each regression from the fixture generator change.
        for name in ('reads', 'queries'):
            path = self.folder/(name+'.csv')
            with path.open(newline='') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                fields = list(reader.fieldnames)
            if 'excluded_users_declared' not in fields:
                fields.append('excluded_users_declared')
            write_csv(path, fields, [dict(r, excluded_users_declared='yes') for r in rows])

    def run_report(self, mode='preflight', path='object', ok=True):
        out = self.folder / (mode+'-'+path)
        r = subprocess.run([sys.executable, str(ROOT/'preflight.py'), str(self.folder), '--read-path', path, '--output', str(out)], capture_output=True, text=True)
        if not ok:
            self.assertNotEqual(r.returncode, 0)
            return r
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(out.with_suffix('.json').read_text())

    def edit(self, name, transform):
        p = self.folder/(name+'.csv')
        with p.open(newline='') as f:
            reader = csv.DictReader(f)
            fields, rows = reader.fieldnames, list(reader)
        write_csv(p, fields, transform(rows))

    def test_preflight_contains_no_paid_findings_in_any_format(self):
        d = self.run_report('preflight')
        for key in ('candidates','spikes','scenarios','scenario_comparisons'):
            self.assertNotIn(key, d)
            for ext in ('html','csv','json'):
                self.assertNotIn('"'+key+'"', (self.folder/('preflight-object.'+ext)).read_text())
        self.assertEqual(len(d['tables']), 180)
        self.assertEqual(len(d['connections']), 18)
        self.assertEqual(d['coverage']['billing']['observed_days'], 92)
        # 1.8M free / (18.6M paid + 1.8M free).
        self.assertEqual(d['free_share'], '0.088235')

    def test_duplicate_billing_is_rejected(self):
        self.edit('billing', lambda rows:rows+[rows[0]])
        self.assertIn('duplicate', self.run_report(ok=False).stderr.lower())

    def test_unknown_free_category_is_rejected(self):
        self.edit('billing', lambda rows:[dict(r, free_type='MYSTERY') if i==0 else r for i,r in enumerate(rows)])
        self.assertIn('free_type', self.run_report(ok=False).stderr)

    def test_missing_exclusion_declaration_blocks_both_paths(self):
        for name, path in [('reads', 'object'), ('queries', 'query')]:
            with self.subTest(path=path):
                p = self.folder/(name+'.csv')
                with p.open(newline='') as f:
                    reader = csv.DictReader(f)
                    fields = [x for x in reader.fieldnames if x != 'excluded_users_declared']
                    rows = [{k:v for k,v in r.items() if k in fields} for r in reader]
                write_csv(p, fields, rows)
                d = self.run_report(path=path)
                self.assertIn('loader statements were not excluded, so reads cannot be trusted', d['full_report_coverage'])

    def test_one_no_declaration_blocks_both_paths(self):
        for name, path in [('reads', 'object'), ('queries', 'query')]:
            with self.subTest(path=path):
                self.edit(name, lambda rows:[dict(r, excluded_users_declared='no') if i==1 else r for i,r in enumerate(rows)])
                d = self.run_report(path=path)
                self.assertIn('loader statements were not excluded, so reads cannot be trusted', d['full_report_coverage'])

    def test_unedited_mapping_database_is_rejected(self):
        for database in ('WAREHOUSE_DB', 'warehouse_db'):
            with self.subTest(database=database):
                self.edit('mapping', lambda rows:[dict(r, object_name=database+'.S0.T00') if i==0 else r for i,r in enumerate(rows)])
                self.assertIn('WAREHOUSE_DB', self.run_report(ok=False).stderr)

    def test_no_mapping_overlap_blocks_both_paths(self):
        self.edit('mapping', lambda rows:[dict(r, object_name=r['object_name'].replace('DEMO.', 'WRONG.')) for r in rows])
        for path in ('object', 'query'):
            with self.subTest(path=path):
                d = self.run_report(path=path)
                self.assertIn('no mapped table appears in read history; the mapping or database name is probably wrong', d['full_report_coverage'])

    def test_empty_ready_history_blocks_both_paths(self):
        for name, path in [('reads', 'object'), ('queries', 'query')]:
            with self.subTest(path=path):
                self.edit(name, lambda rows:[])
                d = self.run_report(path=path)
                self.assertIn('read history is empty', d['full_report_coverage'])

    def test_bad_read_names_are_skipped_counted_and_sampled(self):
        names = ['DEMO.S0.odd-name', 'S0.T00', 'name with spaces', 'DEMO.S0.x()', 'a.b.c.d', 'also-bad']
        self.edit('reads', lambda rows:rows+[dict(rows[0], object_name=n) for n in names])
        d = self.run_report()
        self.assertIn('can screen', d['full_report_coverage'])
        c = d['coverage']['reads']
        self.assertEqual(c['skipped_object_rows'], 6)
        self.assertEqual(c['skipped_object_samples'], names[:5])
        self.assertIn('a mapped table whose real name needs quoting could be affected', c['skipped_object_note'])

    def test_bad_mapping_name_remains_an_error(self):
        self.edit('mapping', lambda rows:[dict(r, object_name='DEMO.S0.odd-name') if i==0 else r for i,r in enumerate(rows)])
        self.assertIn('unsupported object identifier', self.run_report(ok=False).stderr)

    def test_generator_is_repeatable(self):
        before=(self.folder/'billing.csv').read_bytes()
        generate(self.folder)
        self.assertEqual(before,(self.folder/'billing.csv').read_bytes())

    def test_query_text_fallback_is_lower_confidence(self):
        d = self.run_report(path='query')
        self.assertIn('lower-confidence', d['read_evidence'])
        self.assertIn('can screen', d['full_report_coverage'])

    def test_missing_coverage_blocks_read_screening(self):
        self.edit('coverage', lambda rows:[r for r in rows if r['input']!='reads'])
        self.assertIn('cannot screen', self.run_report()['full_report_coverage'])

    def test_unconfirmed_coverage_blocks_read_screening(self):
        self.edit('coverage', lambda rows:[dict(r, complete='false') for r in rows])
        self.assertIn('cannot screen', self.run_report()['full_report_coverage'])

    def test_missing_read_file_blocks_read_screening(self):
        (self.folder/'reads.csv').unlink()
        d = self.run_report()
        self.assertFalse(d['coverage']['reads']['present'])
        self.assertIn('cannot screen', d['full_report_coverage'])

    def test_query_relations_ignore_comments_literals_and_boundaries(self):
        from preflight import query_objects
        row = dict(query_text="SELECT 'FROM DEMO.S0.T00' -- JOIN DEMO.S0.T01\n FROM DEMO.S0.T000", database_name='DEMO', schema_name='S0')
        self.assertEqual(query_objects(row), {('DEMO','S0','T000')})

    def test_unqualified_and_quoted_query_relations_count(self):
        from preflight import query_objects
        row = dict(query_text='SELECT * FROM "T00" JOIN S0.T01 ON 1=1', database_name='DEMO', schema_name='S0')
        self.assertEqual(query_objects(row), {('DEMO','S0','T00'), ('DEMO','S0','T01')})

    def test_same_findings_in_html_csv_json_and_safe_html(self):
        self.edit('billing', lambda rows:[dict(r, table_name='<script>alert(1)</script>') if r['table_name']=='T00' else r for r in rows])
        d = self.run_report()
        with (self.folder/'preflight-object.csv').open() as f:
            rows = list(csv.DictReader(f))
        reconstructed = [json.loads(r['finding_json']) for r in rows if r['section']=='tables']
        self.assertEqual(reconstructed, d['tables'])
        document = (self.folder/'preflight-object.html').read_text()
        self.assertIn('made-up data, no real account', document)
        self.assertIn('quarterly jobs', document)
        self.assertNotIn('<script>', document)
        self.assertIn('&lt;script&gt;', document)

    def test_generator_omits_pricing_and_preserves_seed(self):
        self.assertFalse((self.folder/'pricing.json').exists())
        self.assertEqual(json.loads((self.folder/'manifest.json').read_text()), {'synthetic':True, 'seed':149})

    def test_paid_flags_are_rejected(self):
        for option in (['--level','full'], ['--pricing','terms.json']):
            r = subprocess.run([sys.executable, str(ROOT/'preflight.py'), str(self.folder), '--output', str(self.folder/'out')] + option, capture_output=True, text=True)
            self.assertEqual(r.returncode, 2)
            self.assertIn('unrecognized arguments', r.stderr)

    def test_monthly_table_and_connection_totals(self):
        d = self.run_report()
        for row in d['connections']:
            amount = sum(t['paid_rows'] for t in d['tables'] if all(t[k]==row[k] for k in ('destination_id','connection_name','month')))
            self.assertEqual(row['paid_rows'], amount)
        self.assertEqual(d['total_rows'], 20400000)
        self.assertEqual(d['free_rows'], 1800000)

if __name__ == '__main__': unittest.main()
