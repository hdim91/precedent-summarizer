import json
from datetime import datetime, timedelta

import pytest
import requests
from urllib.parse import quote

from precedent_summarizer.clients.law_go_kr import LawGoKrClient
from precedent_summarizer.collect.supreme_court import Collector, KST, scan_data


class FakeSession:
    def __init__(self, total=101, invalid=False, detail_invalid=False):
        self.total, self.invalid, self.detail_invalid = total, invalid, detail_invalid
        self.calls = []

    def get(self, url, params, timeout):
        self.calls.append(dict(params))
        response = requests.Response()
        response.status_code = 200
        if 'ID' in params:
            body = {} if self.detail_invalid else {'PrecService': {'판례내용': '원문'}}
        elif self.invalid:
            response._content = b'<html>Error</html>'
            return response
        else:
            display, page = params['display'], params['page']
            rows = [{'판례일련번호': str(i+1), '사건번호': '', '선고일자': '20250101'}
                    for i in range((page-1)*display, min(page*display, self.total))]
            body = {'PrecSearch': {'totalCnt': str(self.total), 'prec': rows}}
        response._content = json.dumps(body, ensure_ascii=False).encode()
        return response


def collector(tmp_path, session, now=None):
    client = LawGoKrClient(oc='<YOUR_KEY>', session=session, min_interval_sec=0)
    return Collector(client, tmp_path/'data'/'raw_cache', now=now)


def test_pagination_resume_and_limit(tmp_path):
    session = FakeSession()
    c = collector(tmp_path, session)
    report = c.run(2025, 2025, limit=2)
    assert report['sum_year_items'] == report['manifest_count'] == 101
    assert report['year_slices'][0]['pages'] == 2
    assert report['year_slices'][0]['snapshot_complete']
    assert report['detail_new'] == report['detail_cached'] == 2
    assert report['empty_field_counts']['판시사항'] == 2
    session.calls.clear()
    again = collector(tmp_path, session).run(2025, 2025, limit=0)
    assert len(session.calls) == 1  # only the independent global count
    assert again['detail_cached'] == 2 and again['detail_new'] == 0
    assert scan_data(tmp_path/'data') == 0


@pytest.mark.parametrize('invalid,detail_invalid', [(True, False), (False, True)])
def test_invalid_responses_not_saved(tmp_path, invalid, detail_invalid):
    c = collector(tmp_path, FakeSession(total=1, invalid=invalid, detail_invalid=detail_invalid))
    report = c.run(2025, 2025)
    assert report['failures']
    assert not list((c.root/'prec_detail').glob('*.json'))
    if invalid:
        assert not list((c.root/'prec_list').rglob('*.json'))


def test_consecutive_failure_cutoff(tmp_path):
    c = collector(tmp_path, FakeSession(total=30, detail_invalid=True))
    report = c.run(2025, 2025)
    assert report['detail_failed'] == 20
    assert c.stopped
    assert list((c.root/'reports').glob('*.json'))


def test_snapshot_next_day_and_old_year_reuse(tmp_path):
    day = datetime(2026, 10, 23, tzinfo=KST)
    first = collector(tmp_path, FakeSession(total=1), day)
    first.run(2025, 2025, stage='list')
    old = next((first.root/'prec_list').rglob('p0001.json'))
    before = old.read_bytes()
    session = FakeSession(total=2)
    report = collector(tmp_path, session, day+timedelta(days=1)).run(2025, 2025, stage='list')
    assert report['manifest_count'] == 2
    assert old.read_bytes() == before
    session.calls.clear()
    report = collector(tmp_path, session, day+timedelta(days=2)).run(2025, 2025, stage='list', recent=0)
    assert len(session.calls) == 1
    assert report['manifest_count'] == 2


def test_incomplete_prior_snapshot_restarts(tmp_path):
    day = datetime(2026, 10, 23, tzinfo=KST)
    c = collector(tmp_path, FakeSession(total=101), day)
    c.run(2025, 2025, stage='list')
    next((c.root/'prec_list').rglob('p0002.json')).unlink()
    session = FakeSession(total=101)
    report = collector(tmp_path, session, day+timedelta(days=1)).run(2025, 2025, stage='list', recent=0)
    assert report['year_slices'][0]['snapshot_complete']
    assert any(f['stage'] == 'snapshot' for f in report['failures'])
    assert len(session.calls) == 3


def test_manifest_dedup_and_report_schema(tmp_path):
    c = collector(tmp_path, FakeSession(total=1))
    report = c.run(2024, 2025, stage='list')
    assert report['manifest_count'] == 1
    assert len((c.root/'manifest'/'prec_ids_org400201.jsonl').read_text(encoding='utf-8').splitlines()) == 1
    assert set(report) == {'run_started', 'run_finished', 'api_total_cnt', 'year_slices',
        'sum_year_items', 'manifest_count', 'detail_cached', 'detail_new', 'detail_failed',
        'failures', 'empty_field_counts', 'detail_unavailable', 'by_data_source', 'security_scan_unmasked_oc'}
    assert report['run_started'].endswith('+09:00')


def test_detail_stage_uses_manifest_and_skips_cache(tmp_path):
    c = collector(tmp_path, FakeSession(total=2))
    c.run(2025, 2025, stage='list')
    report = c.run(2025, 2025, stage='detail', limit=1)
    assert report['detail_new'] == 1
    report = c.run(2025, 2025, stage='detail', limit=1)
    assert report['detail_cached'] == 2 and report['detail_new'] == 1


class SourceSession(FakeSession):
    def __init__(self, total=25, unavailable=True, outcomes=None):
        super().__init__(total=total)
        self.unavailable = unavailable
        self.outcomes = outcomes or {}

    def get(self, url, params, timeout):
        response = super().get(url, params, timeout)
        body = json.loads(response.content)
        if 'ID' in params:
            outcome = self.outcomes.get(params['ID'], 'unavailable' if self.unavailable else 'success')
            if outcome == 'unavailable':
                body = {'Law': '일치하는 판례가 없습니다. ?OC=' + quote('<YOUR_KEY>')}
            elif outcome == 'invalid':
                body = {'Law': '다른 오류'}
            elif outcome == 'nonstring':
                body = {'Law': {}}
        else:
            for row in body['PrecSearch']['prec']:
                row['데이터출처명'] = '국세' if int(row['판례일련번호']) % 2 else '대법원'
        response._content = json.dumps(body, ensure_ascii=False).encode()
        return response


def test_unavailable_markers_resume_and_recheck(tmp_path):
    session = SourceSession()
    c = collector(tmp_path, session)
    report = c.run(2025, 2025)
    assert report['detail_unavailable'] == report['manifest_count'] == 25
    assert not report['failures'] and not c.stopped and c.consecutive == 0
    assert report['by_data_source'] == {
        '국세': dict(listed=13, cached=0, unavailable=13, failed=0),
        '대법원': dict(listed=12, cached=0, unavailable=12, failed=0)}
    marker = c.root/'prec_detail_unavailable'/'1.json'
    original = marker.read_bytes()
    saved = json.loads(original)
    assert set(saved) == {'prec_id', 'data_source', 'checked_at', 'api_message'}
    assert saved['checked_at'].endswith('+09:00')
    assert quote('<YOUR_KEY>') not in saved['api_message']
    assert not (c.root/'prec_detail'/'1.json').exists()
    records = [json.loads(line) for line in (c.root/'manifest'/'prec_ids_org400201.jsonl').read_text(encoding='utf-8').splitlines()]
    assert records[0]['data_source'] == '국세'
    session.calls.clear()
    report = c.run(2025, 2025, stage='detail', limit=0)
    assert report['detail_unavailable'] == 25 and len(session.calls) == 1
    c.run(2025, 2025, stage='detail', limit=1, recheck_unavailable=True)
    assert marker.read_bytes() == original
    session.unavailable = False
    report = c.run(2025, 2025, stage='detail', recheck_unavailable=True)
    assert report['detail_cached'] == report['detail_new'] == 25
    assert report['detail_unavailable'] == 0
    assert marker.read_bytes() == original
    session.calls.clear()
    report = c.run(2025, 2025, stage='detail', recheck_unavailable=True)
    assert report['detail_cached'] == 25 and report['detail_new'] == 0
    assert len(session.calls) == 1


@pytest.mark.parametrize('outcome', ['invalid', 'nonstring'])
def test_other_law_errors_remain_failures(tmp_path, outcome):
    c = collector(tmp_path, SourceSession(total=1, outcomes={'1': outcome}))
    report = c.run(2025, 2025)
    assert report['detail_failed'] == 1 and report['detail_unavailable'] == 0
    assert not list((c.root/'prec_detail_unavailable').glob('*.json'))


def test_mixed_source_totals_and_cached_success_reset(tmp_path):
    outcomes = {str(i): 'invalid' for i in range(1, 41)}
    outcomes['20'] = 'success'
    session = SourceSession(total=40, outcomes=outcomes)
    c = collector(tmp_path, session)
    c.run(2025, 2025, stage='list')
    # Existing success splits two runs of nineteen errors; next error stops at 20.
    from precedent_summarizer.collect.supreme_court import atomic_json
    atomic_json(c.root/'prec_detail'/'20.json', {'PrecService': {'판례내용': '원문'}})
    report = c.run(2025, 2025, stage='detail')
    assert report['detail_failed'] == 39 and report['detail_cached'] == 1
    assert report['manifest_count'] == sum(report[k] for k in ('detail_cached', 'detail_unavailable', 'detail_failed'))
    assert sum(v['failed'] for v in report['by_data_source'].values()) == 39
    assert c.stopped and c.consecutive == 20
    c.consecutive = 19
    c.fetch(c.root/'prec_detail'/'20.json', 'PrecService', lambda: pytest.fail('cache requested'))
    assert c.consecutive == 0


def test_security_scan_scope(tmp_path, monkeypatch):
    import precedent_summarizer.collect.supreme_court as module
    c = collector(tmp_path, SourceSession(total=1))
    c.run(2025, 2025)
    # Stale raw is excluded by default; reports are always inspected.
    stale = c.root/'prec_detail'/'999.json'
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text('?OC=' + quote('<YOUR_KEY>'), encoding='utf-8')
    old_report = c.root/'reports'/'old.json'
    old_report.write_text('?OC=' + quote('<YOUR_KEY>'), encoding='utf-8')
    report = c.run(2025, 2025, stage='detail')
    assert report['security_scan_unmasked_oc'] == 1
    old_report.unlink()
    report = c.run(2025, 2025, stage='detail')
    assert report['security_scan_unmasked_oc'] == 0
    report = c.run(2025, 2025, stage='detail', full_security_scan=True)
    assert report['security_scan_unmasked_oc'] == 1
    # New raw, manifest and marker paths are explicitly included in the default scan.
    inspected = []
    original_scan = module.scan_data
    def capture(data_dir, *, files=None):
        inspected.extend(files or [])
        return original_scan(data_dir, files=files)
    monkeypatch.setattr(module, 'scan_data', capture)
    other = collector(tmp_path/'other', SourceSession(total=1))
    report = other.run(2025, 2025)
    assert report['security_scan_unmasked_oc'] == 0
    assert {p.parent.name for p in inspected} >= {'manifest', 'prec_detail_unavailable', 'reports'}
    assert any(p.name == 'p0001.json' for p in inspected)
