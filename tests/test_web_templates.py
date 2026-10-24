from fastapi.testclient import TestClient
from precedent_summarizer.web.app import create_app
from test_web import make_db


def test_index_template_and_static(tmp_path):
    with TestClient(create_app(make_db(tmp_path))) as client:
        response=client.get('/')
        assert response.status_code==200
        for token in ('id="search-form"', 'id="q"', 'id="year_from"', 'id="year_to"',
                      'id="case_type"', 'id="data_source"', 'id="has_summary"', 'id="version"',
                      'id="stats"', 'id="results-body"', 'id="pagination"', '연구용 자동 요약 — 원문을 확인하세요'):
            assert token in response.text
        assert client.get('/static/app.css').status_code==200
        script=client.get('/static/app.js')
        assert script.status_code==200
        assert 'innerHTML' not in script.text and 'insertAdjacentHTML' not in script.text
        assert 'prefers-color-scheme:dark' in client.get('/static/app.css').text


def test_detail_template_containers(tmp_path):
    with TestClient(create_app(make_db(tmp_path))) as client:
        response=client.get('/precedents/1')
        assert response.status_code==200
        for token in ('data-prec-id="1"', 'id="summary-panel"', 'id="summary-tabs"',
                      'id="original-panel"', 'id="original-text"', 'id="section-nav"',
                      'id="evidence-status"', '연구용 자동 요약 — 원문을 확인하세요'):
            assert token in response.text



def test_highlight_javascript():
    import shutil
    import subprocess
    from pathlib import Path
    import pytest
    node=shutil.which('node')
    if node is None:
        pytest.skip('Node is required for JavaScript checks')
    subprocess.run([node, str(Path(__file__).with_name('test_web_highlight.cjs'))], check=True,
                   capture_output=True, text=True, timeout=20)
