# TASK-002b: 날짜 보강·심리불속행 표시 (적재 확장)

- 작성: Claude · 작성일시: 2026-10-24 15:12 KST
- 담당: Codex · 브랜치: `codex/TASK-002b-date-dismissal`
- 상태: 대기

## 목표
요약 대상 선정(최신순·요약 가치)을 위해 `precedents`에 4개 컬럼을 채운다(schema v3): `case_year`, `decision_date_inferred`, `date_inferred_from`, `is_summary_dismissal`.

## 배경 (2026-10-24 실측, 적재 DB 기준)
- 선고일자 자리표시값(`0001.01.01`) 3,426건은 전부 `근로복지공단산재판례`. 상세의 사건번호는 채워져 있고 접수연도 2013~2024에 분포(최신 사건 포함).
- 이들 본문 끝에 선고일 표기가 있다. 예: `…주문과 같이 판결한다.\n2010. 3. 11.\n재판장 대법관 …`
- 3,426건 중 2,448건이 심리불속행 기각(`상고심절차에 관한 특례법 제4조`… `같은 법 제5조에 의하여 상고를 기각`), 본문 중앙값 298자 → 요약 가치 없음. 대법원 출처 2016~2026년에는 연 0~57건.

## 요구사항
1. **스키마 보강(기존 DB 호환)**: `loader` 시작 시 `PRAGMA table_info(precedents)`로 v3 컬럼이 없으면 `ALTER TABLE precedents ADD COLUMN ...`(정의는 `schemas/db.sql` v3와 동일). 이어서 `CREATE INDEX IF NOT EXISTS idx_prec_case_year ON precedents(case_year)`, `idx_prec_date_inf ON precedents(decision_date_inferred)`. `db.sql` 자체는 수정 금지(Claude 소유) — 새 DB 생성 시에는 `db.sql` v3가 이미 컬럼을 포함한다.
2. **`normalize.py`에 순수 함수 추가**
   - `case_year(case_no) -> int | None`: 앞부분 `^\s*(\d{4})`(1940~현재연도+1 범위만), 아니면 None. 예: `2023두57982`→2023, `64도126`→None(2자리 연도는 추정하지 않음).
   - `infer_decision_date(full_text_clean) -> str | None`: 본문 **마지막 1,000자** 안에서 `(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.` 중 **마지막** 일치를 선고일로 보고 `YYYY-MM-DD`(유효 날짜·1948 이상만). 단, 해당 일치 뒤 200자 안에 `대법관`이 있어야 한다(서명부 근거). 없으면 None.
   - `is_summary_dismissal(full_text_clean) -> bool`: 공백 제거본에 `상고심절차에관한특례법제4조`가 있고 `같은법제5조에의하여` 또는 `특례법제5조`가 있으며, `【이유】` 구획 길이 1,500자 이하.
3. **적재 규칙**: 모든 행에 `case_year`, `is_summary_dismissal` 계산. `decision_date_inferred`/`date_inferred_from='body_signature'`는 `date_status='placeholder'`인 행에만(정상 날짜 행은 NULL). `decision_date`·`date_status`는 바꾸지 않는다(원 데이터 보존).
4. **멱등·재적재**: 새 컬럼 값이 기존과 다르면 `updated`. 이번 변경 후 1회 전체 재실행 시 v3 컬럼이 비어 있는 행은 모두 `updated`.
5. **리포트 정리**: 기존 `errors`에 들어가던 `Other HTML tags ...` 경고는 `warnings`로 분리(적재 실패와 구분). 리포트에 `inferred_dates`(건수), `summary_dismissals`(건수) 추가.

## 변경 금지
- `docs/RULES.md`, `docs/INTENT.md`, `docs/DECISIONS.md`, `src/precedent_summarizer/schemas/`, `engine/`, `prompts/`, `common/security.py`, `clients/`, `scripts/hooks/`, `data/raw_cache/**`

## 보안 체크
- [ ] `.env` 미열람·키 미출력, 로그 마스킹 경유, 테스트는 tmp 가짜 데이터

## 완료 조건
- [ ] 단위 테스트: `case_year`(4자리·2자리·빈 값·범위 밖), `infer_decision_date`(서명부 있음/없음, 본문 중간 날짜 무시, 무효 날짜), `is_summary_dismissal`(전형 문구, 이유가 긴 판결은 False)
- [ ] 통합 테스트: v2 DB(새 컬럼 없음)에 실행 → 컬럼 추가·값 채움, 재실행 시 `unchanged`
- [ ] `pytest` 통과. 실제 재적재는 사용자 PC(Claude 원격 셸은 I/O 병목)

## 질문 (Codex → Claude)
-

## 완료 보고 (Codex 작성)
- 완료 일시(KST):
- 변경 파일:
- 검증 결과:
- 남은 문제:
