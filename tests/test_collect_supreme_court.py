import json
from datetime import datetime, timedelta

import pytest
import requests

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
        'failures', 'empty_field_counts'}
    assert report['run_started'].endswith('+09:00')


def test_detail_stage_uses_manifest_and_skips_cache(tmp_path):
    c = collector(tmp_path, FakeSession(total=2))
    c.run(2025, 2025, stage='list')
    report = c.run(2025, 2025, stage='detail', limit=1)
    assert report['detail_new'] == 1
    report = c.run(2025, 2025, stage='detail', limit=1)
    assert report['detail_cached'] == 2 and report['detail_new'] == 1
