"""Seeded, made-up metadata; never connects to anything."""
import argparse
import calendar
import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path


def write_csv(path, fields, rows):
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def generate(folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    rng = random.Random(149)
    billing, mapping, reads, queries, connections = [], [], [], [], []
    quiet = {0, 1, 2, 3, 10, 11, 12, 13}
    for c in range(6):
        connections.append(dict(connection_id=f'id{c}', group_id='d0', connection_name=f'connection_{c}'))
    for t in range(60):
        c = t // 10
        identity = dict(destination_id='d0', connection_name=f'connection_{c}', schema_name=f'S{c}', table_name=f'T{t:02}')
        obj = f'DEMO.S{c}.T{t:02}'
        mapping.append(dict(identity, object_name=obj))
        for month in (8, 9, 10):
            days = calendar.monthrange(2026, month)[1]
            paid = 300000 if t in (20, 30, 40) and month == 10 else 100000
            for day in range(1, days + 1):
                dt = date(2026, month, day).isoformat()
                for category, total in [('PAID', paid), ('SYSTEM', 10000)]:
                    n = total // days + (day <= total % days)
                    billing.append(dict(identity, measured_date=dt, sync_type='INCREMENTAL', free_type=category, incremental_rows=n, updated_at=dt+'T12:00:00Z'))
        if t not in quiet:
            # Sparse events deliberately do not define the covered window.
            for day in (rng.randint(2, 10), 80):
                dt = (date(2026, 8, 1) + timedelta(days=day)).isoformat()+'T12:00:00Z'
                qid = f'q{t}_{day}'
                reads.append(dict(excluded_users_declared='yes', query_id=qid, query_start_time=dt, object_name=obj))
                queries.append(dict(excluded_users_declared='yes', query_id=qid, start_time=dt, database_name='DEMO', schema_name=f'S{c}', query_text=f'SELECT COUNT(*) FROM {obj}', execution_status='SUCCESS'))
    logs = [dict(id=f'e{c}', time='2026-10-05T12:00:00Z', connection_id=f'id{c}', message_event='status') for c in (2, 3)]
    coverage = [dict(input=name, start_date='2026-08-01', end_date='2026-10-31', complete='true') for name in ('billing', 'reads', 'queries', 'logs')]
    for name, rows in [('billing', billing), ('mapping', mapping), ('reads', reads), ('queries', queries), ('connections', connections), ('logs', logs), ('coverage', coverage)]:
        write_csv(folder/(name+'.csv'), list(rows[0]), rows)
    (folder/'manifest.json').write_text(json.dumps({'synthetic': True, 'seed': 149}, indent=2)+'\n')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('folder', type=Path)
    generate(p.parse_args().folder)
