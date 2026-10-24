-- 배치 요약 원장 (Claude 소유, 2026-10-24). 엔진이 CREATE IF NOT EXISTS로 생성.
CREATE TABLE IF NOT EXISTS batch_runs (
    batch_id        TEXT PRIMARY KEY,             -- Anthropic Message Batch ID
    variant         TEXT NOT NULL,                -- blind | official
    created_at      TEXT NOT NULL,
    status          TEXT NOT NULL,                -- submitted | ended | collected
    n_requests      INTEGER NOT NULL,
    est_cost_usd    REAL NOT NULL,                -- 제출 시 추정
    actual_cost_usd REAL,                         -- 수거 후 실측 합계
    note            TEXT
);
CREATE TABLE IF NOT EXISTS batch_items (
    batch_id      TEXT NOT NULL REFERENCES batch_runs(batch_id),
    custom_id     TEXT NOT NULL,
    prec_id       TEXT NOT NULL,
    variant       TEXT NOT NULL,
    model         TEXT NOT NULL,
    attempt       INTEGER NOT NULL,               -- 1: 1차, 2: 검증 실패 재시도(상위 모델)
    est_cost_usd  REAL NOT NULL,
    result_type   TEXT,                           -- succeeded | errored | canceled | expired
    verify_passed INTEGER,
    cost_usd      REAL,                           -- 실측(usage × 배치 단가)
    error         TEXT,                           -- 마스킹된 메시지
    PRIMARY KEY (batch_id, custom_id)
);
CREATE INDEX IF NOT EXISTS idx_bitems_prec ON batch_items(prec_id, variant);

-- 배치 외 API 비용(평가 채점 등). 예산 상한 계산에 포함(D-023)
CREATE TABLE IF NOT EXISTS extra_costs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT NOT NULL,
    purpose     TEXT NOT NULL,                  -- 예: eval_judge
    model       TEXT,
    cost_usd    REAL NOT NULL,
    note        TEXT
);
