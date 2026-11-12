"""Local metadata preflight. Standard library only; no network or credentials."""
import argparse
import csv
from collections import defaultdict
from datetime import date
from decimal import Decimal
import html
import json
from pathlib import Path
import re

IDENTITY = ('destination_id', 'connection_name', 'schema_name', 'table_name')
FREE = set('INITIAL_SYNC CONNECTOR_TRIAL ACCOUNT_TRIAL TABLE_TRIAL NON_CBP_ACCOUNT FREE_RESYNC PROMOTION SYSTEM PRIVATE_PREVIEW FREE_DBT FREE_PLAN CAP_PROMOTION LDP_LIMITED_RESYNC REFUND TRANSFORMATION_TRIAL ACTIVATION_TRIAL FREE_ACTIVATION'.split())
LIMITS = [
    'No reads observed is evidence within a covered window, never proof that a table has no purpose.',
    'Indirect readers this tool cannot see include shares, quarterly jobs, retention duties, and reads outside the exported account or window.',
    'Other automated readers (transformation jobs, backup or copy jobs, catalog or quality scanners) still count as reads and may hide tables with no business readers; customers may add those users to the same warehouse exclusion list.',
    'Every removal is a candidate, confirm with the table owner. No automatic changes are suggested or made.',
    'Lowering sync frequency alone is not a saving.',
    'Prices are customer supplied assumptions, not an invoice guarantee. Warehouse compute, transformations, taxes and other charges are excluded.',
    'Coverage is customer attested; earliest and latest activity do not prove complete history. Missing privileges, export limits, latency, name changes and unsupported operations can hide reads.',
    'A same-month log match confirms co-occurrence only; cause and table attribution remain unproven.',
    'In our own trial run (one Snowflake trial account, 12 November 2026) a query that only counted rows (SELECT COUNT(*)) left no entry in object-level read history, while queries that selected columns did. A table that people only ever count can therefore appear as no reads observed.',
    'Renewal savings assume the same rows, rates and discount, with the current minimum/fixed commitment removed and renegotiable. No refund of a current commitment is assumed.'
]
REQUIRED = {
    'billing': set(IDENTITY) | {'measured_date','sync_type','free_type','incremental_rows','updated_at'},
    'connections': {'connection_id','group_id','connection_name'},
    'mapping': set(IDENTITY) | {'object_name'},
    'logs': {'id','time','connection_id','message_event'},
    'reads': {'query_id','query_start_time','object_name','excluded_users_declared'},
    'queries': {'query_id','start_time','query_text','database_name','schema_name','execution_status','excluded_users_declared'},
    'coverage': {'input','start_date','end_date','complete'}
}


def load(folder, name):
    p = folder/(name+'.csv')
    if not p.exists():
        if name == 'billing':
            raise ValueError('billing.csv is required')
        return [], False, set()
    with p.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(name+': missing CSV header')
        fields = [x.strip().lower() for x in reader.fieldnames]
        required = REQUIRED[name] - ({'excluded_users_declared'} if name in ('reads','queries') else set())
        if len(fields) != len(set(fields)) or not required <= set(fields):
            raise ValueError(name+': duplicate or missing columns: '+', '.join(sorted(REQUIRED[name])))
        reader.fieldnames = fields
        rows = []
        for row in reader:
            if None in row or any(v is None for v in row.values()):
                raise ValueError(name+': malformed CSV row')
            rows.append({k:v.strip() for k,v in row.items()})
    return rows, True, set(fields)


def dt(value):
    return date.fromisoformat(value[:10])


def identity(row):
    return tuple(row[k] for k in IDENTITY)


def obj_parts(value):
    """Preserve quoted case; normalize unquoted Snowflake identifiers."""
    token = r'(?:"(?:[^"]|"")+"|[A-Za-z_][A-Za-z0-9_$]*)'
    if not re.fullmatch(token+r'(?:\s*\.\s*'+token+r')*', value):
        raise ValueError('unsupported object identifier; use simple or quoted identifiers')
    return tuple(x[1:-1].replace('""','"') if x.startswith('"') else x.upper() for x in re.findall(token,value))


def query_objects(row):
    # Remove comments and literals before recognizing FROM/JOIN relation tokens.
    sql = re.sub(r"--[^\n]*|/\*.*?\*/|'(?:''|[^'])*'|\$\$.*?\$\$", ' ', row['query_text'], flags=re.S)
    token = r'(?:"(?:[^"]|"")+"|[A-Za-z_][A-Za-z0-9_$]*)'
    relation = token+r'(?:\s*\.\s*'+token+r'){0,2}'
    found = set()
    for m in re.finditer(r'\b(?:FROM|JOIN)\s+('+relation+r')(?![A-Za-z0-9_$])', sql, re.I):
        parts = obj_parts(m.group(1))
        # QUERY_HISTORY database/schema values already contain resolved names.
        if len(parts)==1 and row['database_name'] and row['schema_name']:
            parts=(row['database_name'], row['schema_name'])+parts
        elif len(parts)==2 and row['database_name']:
            parts=(row['database_name'],)+parts
        if len(parts)==3:
            found.add(parts)
    return found


def analyze(folder, read_path):
    data, exists, fields = {}, {}, {}
    for name in REQUIRED:
        data[name],exists[name],fields[name]=load(folder,name)
    cov = {}
    for r in data['coverage']:
        if r['input'] in cov or r['input'] not in ('billing','reads','queries','logs'):
            raise ValueError('duplicate or unknown coverage input')
        if dt(r['start_date'])>dt(r['end_date']) or r['complete'].lower() not in ('true','false'):
            raise ValueError('invalid coverage dates or complete flag')
        cov[r['input']]={'start':dt(r['start_date']).isoformat(), 'end':dt(r['end_date']).isoformat(), 'complete':r['complete'].lower()=='true'}
    coverage={}
    timefields={'billing':'measured_date','reads':'query_start_time','queries':'start_time','logs':'time'}
    for name in REQUIRED:
        dates=sorted({dt(r[timefields[name]]).isoformat() for r in data[name]}) if name in timefields else []
        c=cov.get(name,{})
        coverage[name]=dict(c, present=exists[name], records=len(data[name]), observed_days=len(dates), observed_start=dates[0] if dates else None, observed_end=dates[-1] if dates else None)
        if name in timefields:
            coverage[name]['declared_days']=(dt(c['end'])-dt(c['start'])).days+1 if c else 0
            if dates and c and (dates[0]<c['start'] or dates[-1]>c['end']):
                raise ValueError(name+': activity outside declared coverage')
    paid=defaultdict(int)
    free=total=0
    seen=set()
    for r in data['billing']:
        if any(not r[k] for k in IDENTITY):
            raise ValueError('empty billing identity')
        key=identity(r)+(r['measured_date'],r['sync_type'],r['free_type'])
        if key in seen:
            raise ValueError('duplicate billing grain; export latest records only')
        seen.add(key)
        n=int(r['incremental_rows'])
        if n<0:
            raise ValueError('negative incremental_rows')
        category=r['free_type']
        if category!='PAID' and category not in FREE:
            raise ValueError('unknown free_type: '+category)
        month=dt(r['measured_date']).isoformat()[:7]
        # Include zero-paid tables in preflight so free-only tables remain visible.
        paid[identity(r)+(month,)]+=n if category=='PAID' else 0
        total+=n
        free+=n if category!='PAID' else 0
    table_rows=[dict(zip(IDENTITY,k[:4]), month=k[4],paid_rows=n) for k,n in paid.items()]
    table_rows.sort(key=lambda r:(r['month'],-r['paid_rows'],identity(r)))
    cp=defaultdict(int)
    for k,n in paid.items(): cp[(k[0],k[1],k[4])]+=n
    conn_rows=[dict(destination_id=k[0],connection_name=k[1],month=k[2],paid_rows=n) for k,n in cp.items()]
    conn_rows.sort(key=lambda r:(r['month'],-r['paid_rows'],r['connection_name']))
    mapping={}
    objects={}
    for r in data['mapping']:
        key=identity(r)
        obj=obj_parts(r['object_name'])
        if not r['object_name'].startswith('"') and obj[0]=='WAREHOUSE_DB':
            raise ValueError('mapping contains placeholder database WAREHOUSE_DB; replace it with the actual destination database')
        if len(obj)!=3 or key in mapping or obj in objects:
            raise ValueError('mapping must be unique, fully qualified and unambiguous')
        mapping[key]=obj
        objects[obj]=key
    read_name='reads' if read_path=='object' else 'queries'
    declared=('excluded_users_declared' in fields[read_name] and
              all(r.get('excluded_users_declared')=='yes' for r in data[read_name]))
    ready=exists[read_name] and cov.get(read_name,{}).get('complete',False) and declared
    reason=''
    if not declared:
        reason='loader statements were not excluded, so reads cannot be trusted'
    elif not ready:
        reason='a present read export and an attested complete window are required'
    read_objects=set()
    skipped=[]
    for r in data[read_name]:
        if read_path=='object':
            try:
                parts=obj_parts(r['object_name'])
            except ValueError:
                parts=()
            if len(parts)!=3:
                skipped.append(r['object_name'])
                continue
            read_objects.add(parts)
        elif r['execution_status'].upper()=='SUCCESS':
            read_objects.update(query_objects(r))
    if read_path=='object':
        coverage[read_name].update(skipped_object_rows=len(skipped), skipped_object_samples=skipped[:5],
            skipped_object_note='Skipped names cannot be matched; a mapped table whose real name needs quoting could be affected.')
    coverage[read_name]['excluded_users_declared']=declared
    if ready and not data[read_name]:
        ready=False
        reason='read history is empty'
    elif ready and not set(objects).intersection(read_objects):
        ready=False
        reason='no mapped table appears in read history; the mapping or database name is probably wrong'
    possible=('Full report can screen no-observed-read candidates within the attested read window; pricing also requires complete billing months, verified mappings and customer terms.' if ready else 'Full report cannot screen no-observed-read candidates: '+reason+'.')
    report={'level':'preflight','sample_notice':'made-up data, no real account' if (folder/'manifest.json').exists() and json.loads((folder/'manifest.json').read_text()).get('synthetic') is True else 'Customer metadata; not verified against an invoice', 'limits':LIMITS,'coverage':coverage,'tables':table_rows,'connections':conn_rows,'free_rows':free,'total_rows':total,'free_share':format(Decimal(free)/Decimal(total),'.6f') if total else '0.000000','read_evidence':'object-level ACCESS_HISTORY, subject to documented exclusions' if read_path=='object' else 'lower-confidence query-text fallback; not lineage and not a complete SQL parser','full_report_coverage':possible+' Spikes need adjacent complete billing months; logs may cover only seven days after initial sync. Log absence cannot rule out an event.'}
    return report


def render(report, output):
    output.parent.mkdir(parents=True,exist_ok=True)
    output.with_suffix('.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    # A section/value CSV is lossless for every finding, including nested evidence.
    records=[]
    for section,value in report.items():
        for item in value if isinstance(value,list) else [value]:
            records.append({'section':section,'finding_json':json.dumps(item,ensure_ascii=False,sort_keys=True)})
    with output.with_suffix('.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['section','finding_json']);w.writeheader();w.writerows(records)
    esc=lambda v:html.escape(str(v),quote=True)
    parts=['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Local bill audit</title><style>body{font:16px/1.55 system-ui,sans-serif;color:#162d36;background:#f6f5ef;margin:0;padding:24px}main{max-width:1160px;margin:auto}h1,h2{line-height:1.2}h1{font-size:36px}aside{border:2px solid #a65f16;padding:16px;background:#fff4dc}table{border-collapse:collapse;font-size:14px;width:100%}td,th{padding:8px;border-bottom:1px solid #cbd4d4;text-align:left;vertical-align:top;overflow-wrap:anywhere}th{background:#e3edeb}section{margin:30px 0;overflow:auto}pre{white-space:pre-wrap;overflow-wrap:anywhere}.notice{font-weight:bold;color:#82501c}li{margin:5px 0}@media print{body{padding:0}section{overflow:visible}tr{break-inside:avoid}}</style><main>']
    parts += ['<p class="notice">'+esc(report['sample_notice'])+'</p>','<h1>Local bill audit · '+esc(report['level'])+'</h1>','<aside><h2>Limits</h2><ul>'+''.join('<li>'+esc(x)+'</li>' for x in report['limits'])+'</ul></aside>']
    for section,value in report.items():
        if section in ('limits','sample_notice','level'):continue
        parts.append('<section><h2>'+esc(section.replace('_',' ').capitalize())+'</h2>')
        if isinstance(value,list) and value and isinstance(value[0],dict):
            fields=list(value[0])
            parts.append('<table><thead><tr>'+''.join('<th>'+esc(k.replace('_',' '))+'</th>' for k in fields)+'</tr></thead><tbody>')
            for row in value:
                parts.append('<tr>'+''.join('<td>'+esc(json.dumps(row[k],ensure_ascii=False) if isinstance(row[k],(dict,list)) else row[k])+'</td>' for k in fields)+'</tr>')
            parts.append('</tbody></table>')
        elif isinstance(value,dict):
            parts.append('<pre>'+esc(json.dumps(value,indent=2,ensure_ascii=False))+'</pre>')
        else:parts.append('<p>'+esc(value if value else 'No findings with the available coverage.')+'</p>')
        parts.append('</section>')
    parts.append('</main></html>')
    output.with_suffix('.html').write_text('\n'.join(parts)+'\n',encoding='utf-8')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('folder',type=Path)
    p.add_argument('--read-path',choices=['object','query'],default='object')
    p.add_argument('--output',required=True,type=Path,help='output basename, without extension')
    args=p.parse_args()
    try:
        report=analyze(args.folder,args.read_path)
        render(report,args.output)
    except (ValueError,KeyError,OSError,TypeError) as e:
        p.exit(2,'Input error: '+str(e)+'\n')
    print('Wrote HTML, CSV and JSON reports.')


if __name__=='__main__':main()
