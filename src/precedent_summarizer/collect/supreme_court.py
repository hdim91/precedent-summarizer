"""Immutable Supreme Court snapshots and resumable detail collection."""
from __future__ import annotations

import argparse
import json
import logging
import math
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from precedent_summarizer.clients.law_go_kr import LawGoKrClient, ORG_SUPREME_COURT, save_raw_response
from precedent_summarizer.common.security import MaskedRequestError, install_log_masking
from precedent_summarizer.config import get_settings

KST = timezone(timedelta(hours=9))
FIELDS = ('판시사항', '판결요지', '참조조문', '참조판례', '판례내용')
LOG = logging.getLogger(__name__)


def parse_body(content, key):
    try:
        body = json.loads(content)
        if not isinstance(body, dict) or not isinstance(body.get(key), dict):
            raise ValueError('Missing response envelope')
        result = body[key]
        if key == 'PrecSearch':
            total = int(result['totalCnt'])
            if total < 0:
                raise ValueError('Negative total')
            rows = result.get('prec', [])
            if isinstance(rows, dict):
                rows = [rows]
            if rows in (None, ''):
                rows = []
            if not isinstance(rows, list) or any(not isinstance(r, dict) or not str(r.get('판례일련번호', '')).isdigit() for r in rows):
                raise ValueError('Invalid precedent records')
            if total and not rows:
                raise ValueError('Empty nonzero search page')
        return result
    except (ValueError, TypeError, KeyError, UnicodeError):
        raise MaskedRequestError(ValueError('Invalid ' + key + ' response')) from None


def rows_of(body):
    rows = body.get('prec') or []
    return [rows] if isinstance(rows, dict) else rows


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8', newline='\n')
    tmp.replace(path)


def scan_data(data_dir):
    """Count unsafe OC parameters, never expose matched values or file contents."""
    count = 0
    for path in data_dir.rglob('*') if data_dir.exists() else []:
        if path.is_file() and not path.name.startswith('.env'):
            for match in re.finditer(rb'[?&]OC=([^&\s\"\'<>]+)', path.read_bytes(), re.I):
                count += match.group(1) != b'***'
    return count


class Collector:
    def __init__(self, client, root, *, now=None):
        self.client, self.root = client, Path(root)
        self.now = now or datetime.now(KST)
        self.day = self.now.strftime('%Y%m%d')
        self.consecutive = 0
        self.stopped = False
        self.report = dict(run_started=self.now.isoformat(), run_finished=None, api_total_cnt=None,
                           year_slices=[], sum_year_items=0, manifest_count=0, detail_cached=0,
                           detail_new=0, detail_failed=0, failures=[], empty_field_counts={f: 0 for f in FIELDS})

    def failure(self, exc, stage, prec_id=''):
        safe = exc if isinstance(exc, MaskedRequestError) else MaskedRequestError(exc)
        self.report['failures'].append(dict(prec_id=prec_id, stage=stage, error=str(safe)))
        self.consecutive += 1
        self.stopped = self.consecutive >= 20
        LOG.warning('%s: %s', stage, safe)

    def fetch(self, path, key, request):
        if path.exists():
            return parse_body(path.read_bytes(), key)
        response = request()
        body = parse_body(response.content, key)
        save_raw_response(response, path)
        self.consecutive = 0
        return body

    def complete(self, snapshot):
        try:
            first = parse_body((snapshot / 'p0001.json').read_bytes(), 'PrecSearch')
            total = int(first['totalCnt'])
            rows = []
            for page in range(1, max(1, math.ceil(total / 100)) + 1):
                body = parse_body((snapshot / f'p{page:04d}.json').read_bytes(), 'PrecSearch')
                if int(body['totalCnt']) != total:
                    return False
                rows.extend(rows_of(body))
            return len(rows) == total and len({str(r['판례일련번호']) for r in rows}) == total
        except (OSError, MaskedRequestError):
            return False

    def choose_snapshot(self, year, to_year, recent):
        parent = self.root / 'prec_list' / 'org400201' / str(year)
        previous = sorted(parent.glob('snap_[0-9]' + '[0-9]' * 7))
        latest = previous[-1] if previous else None
        if latest and latest.name != 'snap_' + self.day and not self.complete(latest):
            self.failure(ValueError(f'Incomplete previous snapshot for {year}'), 'snapshot')
            return parent / ('snap_' + self.day)
        if year >= to_year - recent + 1 or latest is None:
            return parent / ('snap_' + self.day)
        return latest

    def lists(self, from_year, to_year, recent):
        manifest = {}
        for year in range(from_year, to_year + 1):
            if self.stopped:
                break
            snap = self.choose_snapshot(year, to_year, recent)
            info = dict(year=year, snapshot=snap.relative_to(self.root).as_posix(), snapshot_complete=False,
                        total_cnt=0, pages=0, items=0)
            self.report['year_slices'].append(info)
            try:
                def page_request(page):
                    return self.client.search_precedents(org=ORG_SUPREME_COURT, date_from=f'{year}0101',
                                                         date_to=f'{year}1231', display=100, page=page)
                first = self.fetch(snap / 'p0001.json', 'PrecSearch', lambda: page_request(1))
                info['total_cnt'] = int(first['totalCnt'])
                info['pages'] = math.ceil(info['total_cnt'] / 100)
                for page in range(1, max(1, info['pages']) + 1):
                    if self.stopped:
                        break
                    path = snap / f'p{page:04d}.json'
                    try:
                        body = first if page == 1 else self.fetch(path, 'PrecSearch', lambda: page_request(page))
                        if int(body['totalCnt']) != info['total_cnt']:
                            raise ValueError('Snapshot total changed during pagination')
                        rows = rows_of(body)
                        info['items'] += len(rows)
                        for row in rows:
                            ident = str(row['판례일련번호'])
                            manifest.setdefault(ident, dict(prec_id=ident, case_no=row.get('사건번호', ''),
                                decision_date=row.get('선고일자', ''), year=year, list_file=path.relative_to(self.root).as_posix()))
                    except (MaskedRequestError, ValueError, OSError) as exc:
                        self.failure(exc, 'list')
                info['snapshot_complete'] = self.complete(snap)
                if not info['snapshot_complete'] and not self.stopped:
                    self.failure(ValueError(f'Incomplete selected snapshot for {year}'), 'snapshot')
            except (MaskedRequestError, ValueError, OSError) as exc:
                self.failure(exc, 'list')
            LOG.info('Year %s: %s/%s', year, info['items'], info['total_cnt'])
        return list(manifest.values())

    def run(self, from_year=1947, to_year=None, stage='all', limit=None, recent=1):
        # Each invocation owns its counters, including repeated use by callers.
        self.__init__(self.client, self.root, now=self.now)
        to_year = to_year or self.now.year
        if not 1 <= from_year <= to_year <= 9999 or recent < 0 or (limit is not None and limit < 0):
            raise ValueError('Invalid year range, refresh count or limit')
        install_log_masking()
        manifest_path = self.root / 'manifest' / 'prec_ids_org400201.jsonl'
        try:
            # Global total is deliberately independent of selected years for coverage comparison.
            try:
                response = self.client.search_precedents(org=ORG_SUPREME_COURT, display=1, page=1)
                self.report['api_total_cnt'] = int(parse_body(response.content, 'PrecSearch')['totalCnt'])
                self.consecutive = 0
            except (MaskedRequestError, ValueError, OSError) as exc:
                self.failure(exc, 'total')
            if stage == 'detail':
                records = [json.loads(line) for line in manifest_path.read_text(encoding='utf-8').splitlines() if line]
                records = list({str(r['prec_id']): r for r in records if from_year <= int(r['year']) <= to_year}.values())
            else:
                records = self.lists(from_year, to_year, recent)
                manifest_path.parent.mkdir(parents=True, exist_ok=True)
                tmp = manifest_path.with_suffix('.jsonl.tmp')
                tmp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in records), encoding='utf-8', newline='\n')
                tmp.replace(manifest_path)
            self.report['manifest_count'] = len(records)
            attempts = 0
            if stage != 'list':
                for record in records:
                    if self.stopped:
                        break
                    ident = str(record['prec_id'])
                    if not ident.isdigit():
                        self.failure(ValueError('Invalid precedent ID'), 'detail')
                        continue
                    path = self.root / 'prec_detail' / f'{ident}.json'
                    cached = path.exists()
                    if not cached and limit is not None and attempts >= limit:
                        continue
                    try:
                        if not cached:
                            attempts += 1
                        body = self.fetch(path, 'PrecService', lambda: self.client.get_precedent_detail(ident))
                        self.report['detail_cached'] += 1
                        self.report['detail_new'] += not cached
                        for field in FIELDS:
                            self.report['empty_field_counts'][field] += not bool(body.get(field))
                    except (MaskedRequestError, ValueError, OSError) as exc:
                        self.report['detail_failed'] += 1
                        self.failure(exc, 'detail', ident)
        except KeyboardInterrupt:
            self.failure(ValueError('Collection interrupted'), 'run')
        except (OSError, ValueError, KeyError) as exc:
            self.failure(exc, 'run')
        finally:
            self.report['sum_year_items'] = sum(y['items'] for y in self.report['year_slices'])
            self.report['run_finished'] = datetime.now(KST).isoformat()
            violations = scan_data(self.root.parent)
            if violations:
                self.failure(ValueError(f'Unmasked OC scan: {violations} matches'), 'security')
            # Keep the fixed report schema; security scan result is also emitted as a masked log.
            LOG.info('Security scan unmasked OC count: %s', violations)
            out = self.root / 'reports' / f'collect_{self.now:%Y%m%d_%H%M}.json'
            atomic_json(out, self.report)
            LOG.info('Report %s: manifest=%s cached=%s new=%s failed=%s', out,
                     self.report['manifest_count'], self.report['detail_cached'],
                     self.report['detail_new'], self.report['detail_failed'])
        return self.report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--from-year', type=int, default=1947)
    parser.add_argument('--to-year', type=int, default=datetime.now(KST).year)
    parser.add_argument('--stage', choices=('list', 'detail', 'all'), default='all')
    parser.add_argument('--limit', type=int)
    parser.add_argument('--refresh-recent-years', type=int, default=1)
    args = parser.parse_args()
    install_log_masking()
    settings = get_settings()
    try:
        report = Collector(LawGoKrClient(oc=settings.law_api_key), settings.raw_cache_dir).run(
            args.from_year, args.to_year, args.stage, args.limit, args.refresh_recent_years)
    except (ValueError, OSError) as exc:
        LOG.error('%s', MaskedRequestError(exc))
        return 1
    return int(bool(report['failures']))


if __name__ == '__main__':
    raise SystemExit(main())
