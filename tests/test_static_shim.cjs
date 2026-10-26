const assert = require('assert');
const { filterIndex, rewriteHref } = require('../src/precedent_summarizer/export/assets/static_shim.js');
const idx = [
  { prec_id: '10', case_no: '2025다1', case_name: '손해배상', decision_date: '2025-03-01', case_type_name: '민사', data_source: '대법원', detail_status: 'ok', summaries: { v1o: { model: 'claude-sonnet-5-5', one_line: '불법행위 책임 인정' } } },
  { prec_id: '11', case_no: '2026도2', case_name: '사기', decision_date: '2026-01-01', case_type_name: '형사', data_source: '대법원', detail_status: 'ok', summaries: { v1: { model: 'claude-opus-5-5', one_line: '사기죄 성립' } } },
  { prec_id: '12', case_no: '2024두3', case_name: '요양불승인', decision_date: null, decision_date_inferred: '2024-05-05', case_type_name: '일반행정', data_source: '근로복지공단산재판례', detail_status: 'ok', summaries: { v1o: { model: 'claude-sonnet-5-5', one_line: '처분 취소' } } },
];
const P = s => new URLSearchParams(s);
let r = filterIndex(idx, P(''));
assert.deepStrictEqual(r.items.map(x => x.prec_id), ['11', '10', '12']);           // 최신순, 추정 선고일 포함
assert.strictEqual(r.items[0].summary_model, null); assert.strictEqual(r.items[0].summary_versions, 'v1'); // 기본 v1o
assert.strictEqual(filterIndex(idx, P('q=불법행위')).total, 1);                       // 한 줄 요약 검색
assert.strictEqual(filterIndex(idx, P('q=2026도')).items[0].prec_id, '11');           // 사건번호 검색
assert.strictEqual(filterIndex(idx, P('year_from=2025&year_to=2025')).total, 1);
assert.strictEqual(filterIndex(idx, P('has_summary=true&version=v1')).items[0].prec_id, '11');
assert.strictEqual(filterIndex(idx, P('case_type=일반행정')).total, 1);
assert.strictEqual(filterIndex(idx, P('size=1&page=2')).items[0].prec_id, '10');
assert.strictEqual(rewriteHref('/precedents/10?return=%3Fq%3D1'), 'cases/10.html?return=%3Fq%3D1');
assert.strictEqual(rewriteHref('/?page=2'), 'index.html?page=2');
assert.strictEqual(rewriteHref('/'), 'index.html');
assert.strictEqual(rewriteHref('cases/1.html'), null);
console.log('static shim: filter/sort/page, href rewrite passed');
