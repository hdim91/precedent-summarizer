/* 정적 내보내기용 shim (Claude 소유, 2026-10-27).
   app.js(웹 화면)를 수정하지 않고 서버 없이(file://) 동작시키기 위해
   1) /api/* fetch 를 내장 데이터로 응답, 2) 절대경로 링크를 상대경로로, 3) history.pushState 경로 보정을 한다.
   내장 데이터: window.__PS_ROOT__('' 또는 '../'), window.__PS_INDEX__(목록), window.__PS_STATS__, window.__PS_CASE__(상세 페이지) */
(function () {
  'use strict';
  const ROOT = (typeof window !== 'undefined' && window.__PS_ROOT__) || '';

  // ---- 순수 함수: 목록 필터·정렬·페이지 (테스트 대상) ----
  function dateOf(it) { return it.decision_date || it.decision_date_inferred || ''; }
  function filterIndex(index, params) {
    const q = (params.get('q') || '').trim().toLowerCase();
    const version = params.get('version') || 'v1o';
    const yf = parseInt(params.get('year_from') || '', 10), yt = parseInt(params.get('year_to') || '', 10);
    const ct = params.get('case_type') || '', ds = params.get('data_source') || '', hs = params.get('has_summary');
    const page = Math.max(1, parseInt(params.get('page') || '1', 10) || 1);
    const size = Math.min(100, Math.max(1, parseInt(params.get('size') || '20', 10) || 20));
    let rows = index.filter(it => {
      const v = (it.summaries || {})[version];
      if (q) {
        const hay = [it.case_no, it.case_name, ...Object.values(it.summaries || {}).map(s => s.one_line)].join(' ').toLowerCase();
        if (!q.split(/\s+/).every(t => hay.includes(t))) return false;
      }
      const y = parseInt(dateOf(it).slice(0, 4), 10);
      if (yf && !(y >= yf)) return false;
      if (yt && !(y <= yt)) return false;
      if (ct && it.case_type_name !== ct) return false;
      if (ds && it.data_source !== ds) return false;
      if (hs === 'true' && !v) return false;
      if (hs === 'false' && v) return false;
      return true;
    });
    rows.sort((a, b) => (dateOf(a) === '') - (dateOf(b) === '') || dateOf(b).localeCompare(dateOf(a)) || (Number(b.prec_id) - Number(a.prec_id)));
    const items = rows.slice((page - 1) * size, page * size).map(it => {
      const v = (it.summaries || {})[version];
      return { prec_id: it.prec_id, case_no: it.case_no, case_name: it.case_name, decision_date: it.decision_date,
        decision_date_inferred: it.decision_date_inferred, case_type_name: it.case_type_name, data_source: it.data_source,
        detail_status: it.detail_status, summary_model: v ? v.model : null, one_line: v ? v.one_line : null,
        summary_versions: Object.keys(it.summaries || {}).join(',') || null };
    });
    return { total: rows.length, page, size, items };
  }
  function rewriteHref(href) {
    if (!href || !href.startsWith('/')) return null;
    const m = href.match(/^\/precedents\/(\d+)(\?.*)?$/);
    if (m) return ROOT + 'cases/' + m[1] + '.html' + (m[2] || '');
    if (href === '/') return ROOT + 'index.html';
    if (href.startsWith('/?')) return ROOT + 'index.html' + href.slice(1);
    return null;
  }
  if (typeof module !== 'undefined') { module.exports = { filterIndex, rewriteHref }; return; }

  // ---- fetch 대체 ----
  const realFetch = window.fetch ? window.fetch.bind(window) : null;
  const json = (obj, status) => Promise.resolve(new Response(JSON.stringify(obj), { status: status || 200, headers: { 'Content-Type': 'application/json' } }));
  window.fetch = function (url, opts) {
    const u = String(url);
    if (!u.startsWith('/api/')) return realFetch ? realFetch(url, opts) : Promise.reject(new Error('fetch unavailable'));
    const [path, query] = u.split('?');
    if (path === '/api/stats') return json(window.__PS_STATS__ || {});
    if (path === '/api/precedents') return json(filterIndex(window.__PS_INDEX__ || [], new URLSearchParams(query || '')));
    const c = window.__PS_CASE__;
    let m = path.match(/^\/api\/precedents\/(\d+)$/);
    if (m) return c && c.detail.prec_id === m[1] ? json(c.detail) : json({ error: 'not_found' }, 404);
    m = path.match(/^\/api\/precedents\/(\d+)\/summary\/(v1o?)$/);
    if (m) return c && c.detail.prec_id === m[1] && c.summaries[m[2]] ? json(c.summaries[m[2]]) : json({ error: 'not_found' }, 404);
    return json({ error: 'not_found' }, 404);
  };

  // ---- history.pushState 경로 보정(file:// 에서 '/?..'로 경로 변경 불가) ----
  const push = history.pushState.bind(history);
  history.pushState = function (state, title, url) {
    let u = url;
    if (typeof u === 'string' && u.startsWith('/?')) u = location.pathname + u.slice(1);
    return push(state, title, u);
  };

  // ---- 절대경로 링크 → 상대경로 ----
  function fix(a) { const h = a.getAttribute('href'); const n = rewriteHref(h); if (n) a.setAttribute('href', n); }
  function sweep(root) { (root.querySelectorAll ? root.querySelectorAll('a[href^="/"]') : []).forEach(fix); }
  new MutationObserver(muts => {
    for (const mu of muts) {
      if (mu.type === 'attributes' && mu.target.tagName === 'A') fix(mu.target);
      mu.addedNodes && mu.addedNodes.forEach(n => { if (n.nodeType === 1) { if (n.tagName === 'A') fix(n); sweep(n); } });
    }
  }).observe(document.documentElement, { subtree: true, childList: true, attributes: true, attributeFilter: ['href'] });

  // ---- 상세 페이지: '검토 의견 복사' 버튼 ----
  document.addEventListener('DOMContentLoaded', () => {
    sweep(document);
    const c = window.__PS_CASE__;
    const host = document.querySelector('.case-heading-top');
    if (!c || !host) return;
    const versions = Object.keys(c.summaries);
    const text = [
      '[판례 검토 의견]',
      '판례일련번호: ' + c.detail.prec_id, '사건번호: ' + (c.detail.case_no || ''),
      '검토한 요약 버전: ' + (versions.includes('v1o') ? 'v1o' : versions[0] || '없음'),
      '1. 결론 정확(O/X): ', '2. 쟁점 누락(없음/일부/중대): ', '3. 판단 왜곡(O/X): ',
      '4. 원심·대법원 판단 혼동(O/X): ', '5. 소수의견 처리(적절/부적절/해당없음): ', '6. 전반 점수(1~5): ', '7. 의견: '
    ].join('\n');
    const b = document.createElement('button'); b.type = 'button'; b.className = 'copy-review'; b.textContent = '검토 의견 양식 복사';
    const status = document.createElement('span'); status.className = 'small muted'; status.setAttribute('role', 'status');
    b.addEventListener('click', async () => {
      try { await navigator.clipboard.writeText(text); status.textContent = ' 복사됨 — 메일·메신저에 붙여 넣어 작성하세요.'; }
      catch (e) {
        const ta = document.createElement('textarea'); ta.value = text; ta.rows = 10; ta.cols = 50; ta.readOnly = true;
        host.append(ta); ta.select(); status.textContent = ' 자동 복사가 막혀 있습니다. 아래 양식을 직접 복사하세요.';
      }
    });
    host.append(b, status);
  });
})();
