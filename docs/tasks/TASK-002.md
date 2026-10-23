# TASK-002: 정제·적재 (raw 캐시 → SQLite)

- 작성: Claude · 작성일시: 2026-10-23 21:32 KST
- 담당: Codex · 브랜치: `codex/TASK-002-load`
- 상태: 구현·단위/통합 검증 완료, Claude 리뷰·실제 적재 대기

## 목표
수집된 raw 캐시(매니페스트·목록 스냅샷·상세·미제공 마커)를 `schemas/db.sql`(v2) 스키마의 SQLite로 적재한다. 재실행 시 변경분만 반영(멱등).

## 배경 / 관련 결정
- D-005(SQLite+FTS5 trigram), D-016·D-017(미제공 출처는 메타만), TASK-001 v4(선고일자 자리표시값)
- 실측(상세 900건 표본, 2026-10-23): 본문 HTML 태그는 `<br/>`뿐. 구획 표시 `【이    유】`(99%), `【원심판결】`(83%), `【주    문】`(60%), 당사자 표기 다수. 빈 필드: 참조판례 96%, 참조조문 12%, 판결요지 2%. `선고일자`는 `YYYYMMDD`(상세) / `YYYY.MM.DD`(목록).

## 입력
- `Settings.raw_cache_dir` 아래: `manifest/prec_ids_org400201.jsonl`, `prec_list/**`, `prec_detail/{id}.json`, `prec_detail_unavailable/{id}.json`
- 스키마: `src/precedent_summarizer/schemas/db.sql`, 필드 매핑: `schemas/precedent.py`(`LIST_FIELD_MAP`, `DETAIL_FIELD_MAP`)

## 출력 (스키마 고정 — 변경 시 "질문"란에 기재 후 중단)
- DB: `Settings.db_path`(기본 `data/precedents.sqlite`), 테이블 `precedents`, `precedents_fts`, `load_runs`. (`summaries`는 생성만, 쓰지 않음 — Claude 소유)
- 적재 리포트: `data/raw_cache/reports/load_{YYYYMMDD_HHMM}.json` — `{"run_started","run_finished","manifest_count","inserted","updated","unchanged","by_detail_status":{...},"by_data_source":{...},"missing_field_counts":{...},"no_order_section":n,"errors":[{"prec_id","error"}]}`

## 구현 요구사항
- 모듈 `src/precedent_summarizer/load/`(`normalize.py`, `loader.py`), CLI `python -m precedent_summarizer.load.loader [--db PATH] [--rebuild-fts]`
- **행 생성 규칙**: 매니페스트의 모든 `prec_id`에 대해 1행.
  - `prec_detail/{id}.json` 있음 → `detail_status=ok`, 상세 필드 사용(목록과 값이 다르면 상세 우선, 목록에만 있는 `data_source`는 목록 값)
  - 미제공 마커 있음 → `detail_status=unavailable`, 목록 필드만
  - 둘 다 없음 → `detail_status=missing`, 목록 필드만
  - `list_file`은 매니페스트 값
- **정규화(`normalize.py`, 순수 함수 + 단위 테스트)**
  - `clean_text(s)`: `<br/>`·`<br>`·`<br />`(대소문자 무관) → `\n`; 그 외 태그는 제거하지 말고 그대로 두되 리포트에 건수 기록; 줄 끝 공백 제거; 3줄 이상 연속 빈 줄 → 2줄; 앞뒤 공백 제거. **글자 자체(띄어쓰기 포함 본문 문장)는 바꾸지 않는다** — 요약 근거 문장 대조의 기준이 되기 때문.
  - `parse_date(s)`: `YYYYMMDD`·`YYYY.MM.DD`·`YYYY-MM-DD` → `YYYY-MM-DD`. 연도 < 1900(예: `0001.01.01`) → `(None, "placeholder")`, 빈 값 → `(None, "missing")`, 그 외 파싱 실패 → `(None, "missing")` + 리포트 오류.
  - `split_sections(clean)`: `【...】` 헤더를 찾아 `[{"header": 원문 헤더, "header_norm": 공백 제거본, "start": 헤더 시작 오프셋, "end": 다음 헤더 시작 또는 문자열 끝}]`. `has_order_section` = `header_norm == "주문"` 존재 여부.
  - 빈 문자열·공백·문자열 `"null"` → `None`, 해당 정규화 필드명을 `missing_fields`에 추가. 추정·보완 금지(RULES 5장).
- **멱등**: `content_sha256`(raw 상세 바이트 SHA-256)이 같으면 `unchanged`, 다르면 `updated`. 마커·목록만 있는 행은 필드 비교로 판단.
- FTS: content 테이블 방식이므로 적재 후 `INSERT INTO precedents_fts(precedents_fts) VALUES('rebuild')` (또는 트리거). `--rebuild-fts`로 강제 재구축.
- 트랜잭션 단위 1,000행. 중단 후 재실행 시 정상 완결.
- raw 파일은 **읽기만** 한다(쓰기·이동 금지).

## 재사용할 기존 코드
- `config.get_settings()`(경로), `schemas/precedent.py` 매핑, `common/security.install_log_masking`

## 변경 금지
- `docs/RULES.md`, `docs/INTENT.md`, `docs/DECISIONS.md`, `src/precedent_summarizer/schemas/`, `src/precedent_summarizer/engine/`, `prompts/`, `src/precedent_summarizer/common/security.py`, `src/precedent_summarizer/clients/`, `scripts/hooks/`, `data/raw_cache/**`(읽기 전용)

## 보안 체크 (RULES.md 1장)
- [x] `.env` 미열람, 키 값 미출력
- [x] 로그는 마스킹 경유
- [x] 테스트는 tmp 디렉터리의 가짜 raw 파일 사용(실제 `data/` 미사용, 네트워크 미사용)

## 완료 조건
- [x] `normalize.py` 단위 테스트: `<br/>` 변형, 다중 빈 줄, 날짜 3형식·자리표시·빈 값, 구획 분할 오프셋(헤더 사이 텍스트가 정확히 잘리는지), `"null"` 문자열 처리
- [x] `loader` 통합 테스트(tmp): ok/unavailable/missing 3종 행 생성, 재실행 시 `unchanged`, raw 변경 시 `updated`, FTS 검색 1건 이상 적중
- [ ] `pytest` 통과(기본 실행)
- [ ] 실제 적재 실행은 Claude가 수행(D-015)

## 질문 (Codex → Claude)
-

## 완료 보고 (Codex 작성)
- 완료 일시(KST): 2026-10-23 21:41 KST
- 변경 파일: `src/precedent_summarizer/load/__init__.py`, `src/precedent_summarizer/load/normalize.py`, `src/precedent_summarizer/load/loader.py`, `tests/test_normalize.py`, `tests/test_loader.py`, `docs/tasks/TASK-002.md`, `docs/STATE.md`, `docs/worklog/2026-10-23.md`.
- 구현: 순수 정규화 함수(문장 내부 공백·글자 보존), 날짜/구획/누락 필드, raw 목록 매핑 및 상세 우선 적재, ok/unavailable/missing 분류, 상세 SHA-256·메타 필드 비교로 멱등 upsert, 1,000행 커밋·중단 재개, FTS 재구축, load_runs 및 원자적 JSON 보고서, CLI --db/--rebuild-fts. summaries는 스키마 생성 외 쓰지 않음.
- 보고서: 날짜 파싱 실패와 br 외 태그 건수는 고정 스키마의 errors에 prec_id·필드명·건수로 기록. NOT NULL data_source의 원본 빈 값은 빈 문자열로 보관하고 missing_fields에도 기록. FTS는 매 실행(강제 옵션 포함) 재구축해 중단 후 검색 인덱스도 동기화.
- 검증 결과: `src`에서 `python -m pytest ../tests/test_normalize.py ../tests/test_loader.py ../tests/test_collect_supreme_court.py ../tests/test_law_client.py ../tests/test_config.py ../tests/test_security.py -q` → 54 passed(신규 20건). CLI help·git diff --check 정상.
- 통합 검증: 세 상태·상세 우선·자리표시 날짜·정제 전후 필드·raw 바이트 보존·멱등·상세/메타 변경·미제공→정상 전환·FTS 적중·summaries 미작성·load_runs 이력. 1,002건 시나리오에서 별도 연결로 1,000행 커밋 확인, KeyboardInterrupt 후 재실행으로 unchanged 1,000 + inserted 2 검증. 테스트는 전부 작업용 tmp 가짜 raw/DB, 실제 data 및 네트워크 미사용.
- 전체 pytest: 기존 anthropic 의존성 누락으로 테스트 수집 오류, live 2건 제외. 환경 설치 우회 및 실제 적재 실행 없음.
- 커밋: `.git` 쓰기 제한/D-014에 따라 변경은 작업 트리에 유지. Claude 대리 커밋 대상 `codex/TASK-002-load`.
- 남은 문제: Claude 환경에서 전체 pytest 및 실제 raw→DB 적재/건수 검증 필요(D-015). 실제 수집은 계속 진행 중이므로 적재 재실행으로 missing→ok 반영 필요.
