import json
import sqlite3
from pathlib import Path

from precedent_summarizer.load.loader import load


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')


def fixture(root):
    rows = [dict(판례일련번호=str(i), 사건번호='목록번호', 사건명='목록사건',
                 선고일자='0001.01.01' if i == 3 else '2025.01.02', 데이터출처명='목록출처') for i in (1, 2, 3)]
    write(root/'prec_list'/'page.json', {'PrecSearch': {'prec': rows}})
    manifest = root/'manifest'/'prec_ids_org400201.jsonl'
    manifest.parent.mkdir(parents=True)
    manifest.write_text(''.join(json.dumps(dict(prec_id=str(i), list_file='prec_list/page.json'))+'\n' for i in (1,2,3)), encoding='utf-8')
    write(root/'prec_detail'/'1.json', {'PrecService': dict(판례정보일련번호='1', 사건번호='상세번호', 사건명='손해배상청구',
        선고일자='20250102', 판례내용='【주    문】<br/>상고를 기각한다.<br/>【이 유】<br/>문장  보존', 판시사항='null')})
    write(root/'prec_detail_unavailable'/'2.json', {'prec_id': '2'})


def test_load_status_idempotency_updates_fts_and_raw_preservation(tmp_path):
    root, db = tmp_path/'raw', tmp_path/'db.sqlite'
    fixture(root)
    before = {p: p.read_bytes() for p in root.rglob('*') if p.is_file()}
    report = load(root, db)
    assert report['inserted'] == report['manifest_count'] == 3
    assert report['by_detail_status'] == {'ok':1, 'unavailable':1, 'missing':1}
    assert report['by_data_source'] == {'목록출처':3}
    assert report['no_order_section'] == 2
    assert not report['errors']
    with sqlite3.connect(db) as conn:
        conn.row_factory=sqlite3.Row
        row=conn.execute("SELECT * FROM precedents WHERE prec_id='1'").fetchone()
        assert row['case_no']=='상세번호' and row['data_source']=='목록출처'
        assert row['full_text'].count('<br/>') == 3
        assert '문장  보존' in row['full_text_clean']
        assert row['has_order_section']==1 and row['holdings'] is None
        assert 'holdings' in json.loads(row['missing_fields'])
        assert conn.execute("SELECT date_status FROM precedents WHERE prec_id='3'").fetchone()[0]=='placeholder'
        assert conn.execute("SELECT count(*) FROM precedents_fts WHERE precedents_fts MATCH ?", ('손해배상',)).fetchone()[0]==1
        assert conn.execute('SELECT count(*) FROM summaries').fetchone()[0]==0
        loaded_at=row['loaded_at']
    assert all(p.read_bytes()==raw for p,raw in before.items())
    report=load(root, db, rebuild_fts=True)
    assert report['unchanged']==3 and report['inserted']==report['updated']==0
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT loaded_at FROM precedents WHERE prec_id='1'").fetchone()[0]==loaded_at
    path=root/'prec_detail'/'1.json'
    body=json.loads(path.read_text(encoding='utf-8'));body['PrecService']['사건명']='변경사건';write(path,body)
    report=load(root, db)
    assert report['updated']==1 and report['unchanged']==2
    write(root/'prec_detail'/'2.json', {'PrecService': {'사건명':'새상세', '선고일자':'20250103'}})
    report=load(root, db)
    assert report['updated']==1 and report['by_detail_status']['ok']==2
    with sqlite3.connect(db) as conn:
        assert conn.execute('SELECT count(*) FROM load_runs').fetchone()[0]==4


def test_bad_date_tags_invalid_record_and_metadata_change(tmp_path):
    root,db=tmp_path/'raw',tmp_path/'db.sqlite';fixture(root)
    path=root/'prec_detail'/'1.json'
    body=json.loads(path.read_text(encoding='utf-8'))
    body['PrecService'].update(선고일자='bad', 판례내용='<b>보존</b>')
    write(path,body)
    report=load(root,db)
    assert any(e['error']=='Invalid decision_date' for e in report['errors'])
    assert any(e['error']=='Other HTML tags in full_text: 2' for e in report['errors'])
    path=root/'prec_list'/'page.json';body=json.loads(path.read_text(encoding='utf-8'))
    body['PrecSearch']['prec'][2]['사건명']='바뀐 메타';write(path,body)
    report=load(root,db)
    assert report['updated']==1 and report['unchanged']==2
    (root/'prec_detail'/'1.json').write_text('<html>bad</html>',encoding='utf-8')
    report=load(root,db)
    assert any(e['error'].endswith('failed to load record') for e in report['errors'])
    with sqlite3.connect(db) as conn:
        assert conn.execute('SELECT count(*) FROM precedents').fetchone()[0]==3



def test_thousand_row_commit_interruption_and_resume(tmp_path, monkeypatch):
    import precedent_summarizer.load.loader as module
    root,db=tmp_path/'raw',tmp_path/'db.sqlite'
    rows=[{'판례일련번호':str(i), '사건명':'손해배상청구', '데이터출처명':'대법원'} for i in range(1,1003)]
    write(root/'prec_list'/'page.json', {'PrecSearch': {'prec':rows}})
    manifest=root/'manifest'/'prec_ids_org400201.jsonl';manifest.parent.mkdir(parents=True)
    manifest.write_text(''.join(json.dumps(dict(prec_id=str(i),list_file='prec_list/page.json'))+'\n'
                                for i in range(1,1003)),encoding='utf-8')
    original=module.make_row
    def interrupt(root, record, pages, issues):
        if record['prec_id']=='1001':
            # A separate connection sees the first batch before the current run finishes.
            with sqlite3.connect(db) as reader:
                assert reader.execute('SELECT count(*) FROM precedents').fetchone()[0]==1000
            raise KeyboardInterrupt
        return original(root, record, pages, issues)
    monkeypatch.setattr(module,'make_row',interrupt)
    report=load(root,db)
    assert report['inserted']==1000
    assert any(e['error']=='Load interrupted' for e in report['errors'])
    monkeypatch.setattr(module,'make_row',original)
    report=load(root,db)
    assert report['unchanged']==1000 and report['inserted']==2 and not report['errors']
    with sqlite3.connect(db) as conn:
        assert conn.execute('SELECT count(*) FROM precedents').fetchone()[0]==1002
        assert conn.execute("SELECT count(*) FROM precedents_fts WHERE precedents_fts MATCH '損害'").fetchone()[0]==0
        assert conn.execute("SELECT count(*) FROM precedents_fts WHERE precedents_fts MATCH '손해배상'").fetchone()[0]==1002
