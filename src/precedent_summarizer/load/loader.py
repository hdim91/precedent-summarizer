"""Load immutable raw caches into the approved SQLite schema."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
from pathlib import Path
import sqlite3
from uuid import uuid4

from precedent_summarizer.common.security import install_log_masking, mask_secrets
from precedent_summarizer.config import get_settings
from precedent_summarizer.schemas.precedent import LIST_FIELD_MAP, DETAIL_FIELD_MAP
from precedent_summarizer.load.normalize import nullable, clean_text, parse_date, split_sections, other_tag_count, case_year, infer_decision_date, is_summary_dismissal

KST = timezone(timedelta(hours=9))
SCHEMA = Path(__file__).resolve().parents[1] / 'schemas' / 'db.sql'
TEXT_FIELDS = ('holdings', 'official_summary', 'ref_statutes', 'ref_precedents', 'full_text')
LOG = logging.getLogger(__name__)


def stamp():
    return datetime.now(KST).isoformat()


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def cache_path(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or any(p.startswith('.env') for p in path.relative_to(root.resolve()).parts):
        raise ValueError('Invalid raw cache path')
    return path


def make_row(root, record, pages, issues):
    ident = str(record['prec_id'])
    if not ident.isdigit():
        raise ValueError('Invalid precedent ID')
    list_file = record['list_file']
    if list_file not in pages:
        body = read_json(cache_path(root, list_file))['PrecSearch'].get('prec') or []
        if isinstance(body, dict):
            body = [body]
        pages[list_file] = {str(r['판례일련번호']): r for r in body}
    listed = pages[list_file][ident]
    fields = {target: nullable(listed.get(source)) for source, target in LIST_FIELD_MAP.items()}
    path = root / 'prec_detail' / f'{ident}.json'
    marker = root / 'prec_detail_unavailable' / f'{ident}.json'
    raw = None
    if path.exists():
        raw = path.read_bytes()
        detail = json.loads(raw)['PrecService']
        if not isinstance(detail, dict):
            raise ValueError('Invalid PrecService envelope')
        detail_id = detail.get('판례정보일련번호')
        if detail_id is not None and str(detail_id) != ident:
            raise ValueError('Detail ID mismatch')
        fields.update({target: nullable(detail.get(source)) for source, target in DETAIL_FIELD_MAP.items()
                       if target != 'prec_id'})
        status = 'ok'
    else:
        status = 'unavailable' if marker.exists() else 'missing'
    fields['prec_id'] = ident
    # NOT NULL source column stores the original empty value; missing_fields still records it.
    fields['data_source'] = fields.get('data_source') or ''
    date_input = fields.get('decision_date')
    fields['decision_date'], fields['date_status'] = parse_date(date_input)
    if nullable(date_input) is not None and fields['date_status'] == 'missing':
        issues.append(dict(prec_id=ident, error='Invalid decision_date'))
    for field in TEXT_FIELDS:
        fields.setdefault(field, None)
        fields[field + '_clean'] = clean_text(fields[field])
        count = other_tag_count(fields[field])
        if count:
            issues.append(dict(prec_id=ident, error=f'Other HTML tags in {field}: {count}'))
    sections = split_sections(fields['full_text_clean'])
    missing = [field for field, value in fields.items()
               if field not in ('prec_id', 'date_status') and nullable(value) is None]
    fields.update(detail_status=status, sections_json=json.dumps(sections, ensure_ascii=False),
                  has_order_section=int(any(s['header_norm'] == '주문' for s in sections)),
                  missing_fields=json.dumps(missing, ensure_ascii=False),
                  raw_detail_path=path.relative_to(root).as_posix() if raw is not None else None,
                  list_file=list_file, content_sha256=hashlib.sha256(raw).hexdigest() if raw is not None else None,
                  loaded_at=stamp())
    inferred = infer_decision_date(fields['full_text_clean']) if fields['date_status'] == 'placeholder' else None
    fields.update(case_year=case_year(fields.get('case_no')),
                  decision_date_inferred=inferred,
                  date_inferred_from='body_signature' if inferred else None,
                  is_summary_dismissal=int(is_summary_dismissal(fields['full_text_clean'])))
    return fields


def upgrade_schema(conn):
    definitions = {
        'case_year': 'INTEGER',
        'decision_date_inferred': 'TEXT',
        'date_inferred_from': 'TEXT',
        'is_summary_dismissal': 'INTEGER NOT NULL DEFAULT 0',
    }
    columns = {row[1] for row in conn.execute('PRAGMA table_info(precedents)')}
    for column, definition in definitions.items():
        if column not in columns:
            conn.execute(f'ALTER TABLE precedents ADD COLUMN {column} {definition}')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_prec_case_year ON precedents(case_year)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_prec_date_inf ON precedents(decision_date_inferred)')
    return bool(set(definitions) - columns)


def load(root, db_path, *, rebuild_fts=False, report_dir=None):
    """Read raw only. Reports are the sole generated files under raw_cache."""
    install_log_masking()
    root, db_path = Path(root), Path(db_path)
    report = dict(run_started=stamp(), run_finished=None, manifest_count=0, inserted=0,
                  updated=0, unchanged=0, by_detail_status={}, by_data_source={},
                  missing_field_counts={}, no_order_section=0, errors=[], warnings=[], inferred_dates=0, summary_dismissals=0)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    pages = {}
    status_counts, source_counts, missing_counts = Counter(), Counter(), Counter()
    run_id = uuid4().hex
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA.read_text(encoding='utf-8'))
        schema_upgraded = upgrade_schema(conn)
        conn.execute('INSERT INTO load_runs(run_id, started_at) VALUES (?, ?)', (run_id, report['run_started']))
        conn.commit()
        seen = set()
        with (root / 'manifest' / 'prec_ids_org400201.jsonl').open(encoding='utf-8') as manifest:
            for line in manifest:
                if not line.strip():
                    continue
                ident = ''
                try:
                    record = json.loads(line)
                    ident = str(record['prec_id'])
                    if ident in seen:
                        continue
                    seen.add(ident)
                    report['manifest_count'] += 1
                    issues = []
                    row = make_row(root, record, pages, issues)
                    for issue in issues:
                        target = 'warnings' if issue['error'].startswith('Other HTML tags ') else 'errors'
                        report[target].append(issue)
                    old = conn.execute('SELECT * FROM precedents WHERE prec_id=?', (ident,)).fetchone()
                    if old is None:
                        action = 'inserted'
                    elif not schema_upgraded and all(old[k] == v for k, v in row.items() if k != 'loaded_at'):
                        action = 'unchanged'
                    else:
                        action = 'updated'
                    if action != 'unchanged':
                        columns = list(row)
                        updates = ','.join(f'{c}=excluded.{c}' for c in columns if c != 'prec_id')
                        conn.execute(f"INSERT INTO precedents ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)}) "
                                     f'ON CONFLICT(prec_id) DO UPDATE SET {updates}', tuple(row.values()))
                    report[action] += 1
                    status_counts[row['detail_status']] += 1
                    source_counts[row['data_source']] += 1
                    missing_counts.update(json.loads(row['missing_fields']))
                    report['no_order_section'] += not row['has_order_section']
                    report['inferred_dates'] += row['decision_date_inferred'] is not None
                    report['summary_dismissals'] += row['is_summary_dismissal']
                except (ValueError, KeyError, TypeError, OSError, sqlite3.Error) as exc:
                    # Never include a JSON parser's raw document or database values in diagnostics.
                    report['errors'].append(dict(prec_id=ident, error=mask_secrets(type(exc).__name__ + ': failed to load record')))
                if report['manifest_count'] and report['manifest_count'] % 1000 == 0:
                    conn.commit()
        conn.commit()
    except (ValueError, OSError, sqlite3.Error) as exc:
        report['errors'].append(dict(prec_id='', error=mask_secrets(type(exc).__name__ + ': load interrupted')))
    except KeyboardInterrupt:
        report['errors'].append(dict(prec_id='', error='Load interrupted'))
    finally:
        # Rebuild even after interruption so committed rows remain searchable on resume.
        conn.commit()
        try:
            conn.execute("INSERT INTO precedents_fts(precedents_fts) VALUES('rebuild')")
            conn.commit()
        except sqlite3.Error as exc:
            report['errors'].append(dict(prec_id='', error=mask_secrets(type(exc).__name__ + ': FTS rebuild failed')))
        report.update(run_finished=stamp(), by_detail_status=dict(status_counts),
                      by_data_source=dict(source_counts), missing_field_counts=dict(missing_counts))
        conn.execute('UPDATE load_runs SET finished_at=?, stats_json=? WHERE run_id=?',
                     (report['run_finished'], json.dumps(report, ensure_ascii=False), run_id))
        conn.commit()
        conn.close()
        destination = Path(report_dir) if report_dir is not None else root / 'reports'
        destination.mkdir(parents=True, exist_ok=True)
        out = destination / f'load_{datetime.now(KST):%Y%m%d_%H%M}.json'
        tmp = out.with_suffix('.json.tmp')
        tmp.write_text(mask_secrets(json.dumps(report, ensure_ascii=False, indent=2)), encoding='utf-8', newline='\n')
        tmp.replace(out)
    LOG.info('Load inserted=%s updated=%s unchanged=%s errors=%s',
             report['inserted'], report['updated'], report['unchanged'], len(report['errors']))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path)
    parser.add_argument('--rebuild-fts', action='store_true')
    args = parser.parse_args()
    install_log_masking()
    settings = get_settings()
    report = load(settings.raw_cache_dir, args.db or settings.db_path, rebuild_fts=args.rebuild_fts)
    return int(bool(report['errors']))


if __name__ == '__main__':
    raise SystemExit(main())
