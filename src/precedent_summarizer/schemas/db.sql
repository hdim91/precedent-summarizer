-- SQLite 스키마 v1 (Claude 소유). P2(정제·적재)에서 사용. 요약 테이블은 P3에서 추가.
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS precedents (
    prec_id          TEXT PRIMARY KEY,           -- 판례일련번호
    case_no          TEXT,
    case_name        TEXT,
    decision_date    TEXT,                       -- YYYY-MM-DD
    decision_kind    TEXT,
    court_name       TEXT,
    court_type_code  TEXT,
    case_type_name   TEXT,
    case_type_code   TEXT,
    judgment_type    TEXT,
    data_source      TEXT,
    holdings         TEXT,                       -- 판시사항(원문)
    official_summary TEXT,                       -- 판결요지(원문)
    ref_statutes     TEXT,                       -- 참조조문(원문)
    ref_precedents   TEXT,                       -- 참조판례(원문)
    full_text        TEXT,                       -- 판례내용(원문)
    missing_fields   TEXT NOT NULL DEFAULT '[]', -- JSON 배열
    raw_detail_path  TEXT NOT NULL,              -- data/raw_cache 기준 상대경로
    content_sha256   TEXT NOT NULL,              -- raw 상세 본문 해시(재적재·변경 감지)
    fetched_at       TEXT NOT NULL,              -- ISO8601 KST
    loaded_at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_prec_date ON precedents(decision_date);
CREATE INDEX IF NOT EXISTS idx_prec_case_no ON precedents(case_no);

CREATE VIRTUAL TABLE IF NOT EXISTS precedents_fts USING fts5(
    case_no, case_name, holdings, official_summary, full_text,
    content='precedents', content_rowid='rowid', tokenize='trigram'
);

CREATE TABLE IF NOT EXISTS collection_runs (
    run_id        TEXT PRIMARY KEY,
    stage         TEXT NOT NULL,                 -- list | detail | load
    started_at    TEXT NOT NULL,
    finished_at   TEXT,
    params_json   TEXT NOT NULL,                 -- 비밀값 미포함
    stats_json    TEXT                           -- 건수·실패·누락 집계
);

CREATE TABLE IF NOT EXISTS fetch_failures (
    prec_id     TEXT,
    stage       TEXT NOT NULL,
    error       TEXT NOT NULL,                   -- mask_secrets() 거친 문자열만
    occurred_at TEXT NOT NULL,
    resolved    INTEGER NOT NULL DEFAULT 0
);
