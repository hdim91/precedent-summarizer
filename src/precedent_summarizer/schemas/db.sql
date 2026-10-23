-- SQLite 스키마 v2 (Claude 소유, 2026-10-23 21:30 KST). P2(정제·적재)·P3(요약)에서 사용.
-- v1 대비: detail_status/data_source/date_status 추가, raw_detail_path nullable(미제공 출처),
--          정제본(clean)·구획(sections_json) 컬럼 추가, FTS는 정제본 대상, summaries 테이블 추가.
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS precedents (
    prec_id           TEXT PRIMARY KEY,            -- 판례일련번호
    case_no           TEXT,
    case_name         TEXT,
    decision_date     TEXT,                        -- YYYY-MM-DD, 자리표시값(0001.01.01)이면 NULL
    date_status       TEXT NOT NULL,               -- ok | placeholder | missing
    decision_kind     TEXT,                        -- 선고 | 자 | ...
    judgment_type     TEXT,                        -- 판결 | 결정 | ...
    court_name        TEXT,
    court_type_code   TEXT,
    case_type_name    TEXT,
    case_type_code    TEXT,
    data_source       TEXT NOT NULL,               -- 목록의 데이터출처명
    detail_status     TEXT NOT NULL,               -- ok | unavailable | missing
    -- 원문(raw 그대로, <br/> 포함)
    holdings          TEXT,                        -- 판시사항
    official_summary  TEXT,                        -- 판결요지
    ref_statutes      TEXT,                        -- 참조조문
    ref_precedents    TEXT,                        -- 참조판례
    full_text         TEXT,                        -- 판례내용
    -- 정제본(<br/>→\n, 공백 정리). 요약·검증·검색은 정제본 기준
    holdings_clean         TEXT,
    official_summary_clean TEXT,
    ref_statutes_clean     TEXT,
    ref_precedents_clean   TEXT,
    full_text_clean        TEXT,
    sections_json     TEXT,                        -- [{"header","header_norm","start","end"}] (full_text_clean 기준 문자 오프셋)
    has_order_section INTEGER NOT NULL DEFAULT 0,  -- 【주문】 구획 존재 여부
    missing_fields    TEXT NOT NULL DEFAULT '[]',  -- JSON 배열(정규화 필드명)
    raw_detail_path   TEXT,                        -- raw_cache 기준 상대경로(미제공이면 NULL)
    list_file         TEXT NOT NULL,               -- 출처 목록 스냅샷 파일
    content_sha256    TEXT,                        -- raw 상세 본문 해시
    loaded_at         TEXT NOT NULL                -- ISO8601 KST
);
CREATE INDEX IF NOT EXISTS idx_prec_date   ON precedents(decision_date);
CREATE INDEX IF NOT EXISTS idx_prec_caseno ON precedents(case_no);
CREATE INDEX IF NOT EXISTS idx_prec_status ON precedents(detail_status, data_source);

CREATE VIRTUAL TABLE IF NOT EXISTS precedents_fts USING fts5(
    case_no, case_name, holdings_clean, official_summary_clean, full_text_clean,
    content='precedents', content_rowid='rowid', tokenize='trigram'
);

CREATE TABLE IF NOT EXISTS summaries (
    prec_id         TEXT NOT NULL REFERENCES precedents(prec_id),
    version         TEXT NOT NULL,                 -- 프롬프트·스키마 버전(예: v1)
    model           TEXT NOT NULL,
    summary_json    TEXT NOT NULL,                 -- schemas/summary.py 구조
    verify_json     TEXT NOT NULL,                 -- 검증기 결과
    verify_passed   INTEGER NOT NULL,
    input_tokens    INTEGER,
    output_tokens   INTEGER,
    created_at      TEXT NOT NULL,
    PRIMARY KEY (prec_id, version)
);

CREATE TABLE IF NOT EXISTS load_runs (
    run_id        TEXT PRIMARY KEY,
    started_at    TEXT NOT NULL,
    finished_at   TEXT,
    stats_json    TEXT
);
