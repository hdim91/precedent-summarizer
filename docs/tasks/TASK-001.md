# TASK-001: 대법원 판례 전량 수집 (목록 + 상세 → raw 캐시)

- 작성: Claude · 작성일시: 2026-10-23 18:48 KST
- 담당: Codex · 브랜치: `codex/TASK-001-supreme-court-collector`
- 상태: v2 병합 완료(69dc94b) → **v3 구현·단위 검증 완료, Claude 리뷰 대기** (2026-10-23 19:25 KST)

## 목표
law.go.kr Open API에서 **대법원 판례 전량(2026-10-23 실측 totalCnt=75,467)** 의 목록과 상세를 raw 캐시로 수집한다.
중단 후 재실행하면 이어서 진행되고(재개 가능), 이후 실행은 신규분만 받는다(증분).

## 배경 / 관련 결정
- D-003(대법원만·배치), D-004(law.go.kr), D-010(전량 수집), D-008(비밀정보)
- 실측(2026-10-23): `org=400201` 대법원 필터, `prncYd=YYYYMMDD~YYYYMMDD` 선고일자 필터 동작 확인. 1950~1979 대법원 9,035건, 2025년 1,150건.
- **검색 응답 본문의 `판례상세링크`에 인증키(OC)가 그대로 들어 있다** → 저장은 반드시 `save_raw_response()`(마스킹 내장) 사용.

## 입력
- `precedent_summarizer.clients.law_go_kr.LawGoKrClient`
  - `search_precedents(org=ORG_SUPREME_COURT, date_from=, date_to=, display=100, page=)`
  - `get_precedent_detail(prec_id)`
- 실행 인자(CLI): `--from-year`(기본 1947), `--to-year`(기본 올해), `--stage {list,detail,all}`, `--limit N`(시범용), `--refresh-recent-years K`(기본 1: 최근 K년 구간은 오늘 날짜 스냅샷으로 목록을 새로 받아 신규분 확인)

## 출력 (스키마 고정 — 변경 시 "질문"란에 기재 후 중단)
경로 기준: `Settings.raw_cache_dir`(기본 `data/raw_cache/`)
1. 목록 raw: `prec_list/org400201/{YYYY}/snap_{YYYYMMDD}/p{page:04d}.json` — **선고연도 단위로 구간 분할**(페이지 밀림 방지), **수집일 스냅샷 단위로 불변 저장**
   - 스냅샷 선택 규칙(연도별):
     - 갱신 대상 연도(`to_year - K + 1` ~ `to_year`): 오늘 날짜 스냅샷 `snap_{오늘}` 사용. 이미 있으면 그 안의 기존 페이지는 재호출하지 않음(같은 날 재실행 = 재개).
     - 그 외 연도: 기존 스냅샷이 있으면 **가장 최근 스냅샷** 재사용(호출 없음). 없으면 `snap_{오늘}` 생성.
   - 한 스냅샷은 같은 실행에서 1페이지의 `totalCnt` 기준으로 완결돼야 한다. 페이지 일부만 받은 스냅샷이 다음 날 남아 있으면 "미완결"로 리포트하고 새 스냅샷으로 다시 받는다(기존 파일은 삭제하지 않음).
2. 상세 raw: `prec_detail/{판례일련번호}.json`
3. 매니페스트: `manifest/prec_ids_org400201.jsonl` — 한 줄 1건 `{"prec_id","case_no","decision_date","year","list_file"}` (연도별 **선택된 스냅샷**에서 추출, `prec_id` 기준 중복 제거). 매니페스트는 raw가 아닌 파생물이므로 매 실행 재생성(덮어쓰기) 허용 — 임시 파일에 쓴 뒤 교체.
4. 수집 리포트: `reports/collect_{YYYYMMDD_HHMM}.json` —
   `{"run_started","run_finished","api_total_cnt","year_slices":[{"year","snapshot","snapshot_complete","total_cnt","pages","items"}],"sum_year_items","manifest_count","detail_cached","detail_new","detail_failed","failures":[{"prec_id","stage","error"}],"empty_field_counts":{"판시사항":n,...}}`
   - 시각은 KST ISO8601. `error`는 `MaskedRequestError` 메시지(이미 마스킹됨)만.

## 구현 요구사항
- 모듈: `src/precedent_summarizer/collect/supreme_court.py`, CLI: `python -m precedent_summarizer.collect.supreme_court`
- 연도 구간별 1페이지 호출로 `totalCnt`를 얻고 `ceil(totalCnt/100)`페이지 순회.
- **재개·증분**: 이미 존재하는 raw 파일은 재호출하지 않는다. `save_raw_response()`에는 덮어쓰기 옵션이 없다(D-013). 최근 연도 갱신은 위 스냅샷 규칙으로만 한다. 상세(`prec_detail/{id}.json`)는 스냅샷 없이 1회 수집·불변.
- **응답 검증**: HTTP 200이어도 JSON 파싱 실패·`PrecSearch`/`PrecService` 키 없음이면 실패로 기록하고 **저장하지 않는다**(오류 HTML 캐싱 방지).
- 호출 간격 0.1s 이상(클라이언트 기본값 유지), 연속 실패 20건이면 중단하고 리포트 저장.
- 로깅: `install_log_masking()` 호출 후 `logging` 사용. `print`로 URL·응답 원문 출력 금지.
- `--limit`은 상세 단계에서만 적용(시범 수집용).

## 재사용할 기존 코드
- `clients/law_go_kr.py`(`LawGoKrClient`, `save_raw_response`, `ORG_SUPREME_COURT`), `common/security.py`, `config.get_settings()`의 경로 설정
- 원본 패턴 참고: OneDrive `Leagal Tech/CODE/python/src/스토킹처벌법/fetch_precedents.py`, `fetch_precedent_details.py`

## 변경 금지
- `docs/RULES.md`, `docs/INTENT.md`, `docs/DECISIONS.md`, `src/precedent_summarizer/schemas/`, `src/precedent_summarizer/common/security.py`, `src/precedent_summarizer/clients/law_go_kr.py`, `scripts/hooks/`
  (클라이언트 기능이 부족하면 "질문"란에 기재)

## 보안 체크 (RULES.md 1장)
- [x] `.env` 미열람, 키 값 미출력
- [x] 로그·예외 출력은 마스킹 경유(`install_log_masking`, `MaskedRequestError`)
- [x] raw 저장은 `save_raw_response`만 사용(직접 `write_bytes(resp.content)` 금지)
- [x] 테스트에서 실제 키·네트워크 미사용(FakeSession 사용 — `tests/test_law_client.py` 참고)
- [ ] 수집 완료 후 `data/` 전체에서 `[?&]OC=` 뒤에 `***` 아닌 값이 없는지 검사 결과를 리포트에 포함

## 완료 조건
- [x] 단위 테스트(`tests/test_collect_supreme_court.py`): 페이지 계산, 재개(기존 파일 스킵), 비정상 응답 미저장, 매니페스트 중복 제거, 리포트 스키마
- [ ] 시범: `--from-year 2025 --to-year 2025 --limit 50` 실행 → 리포트 첨부(건수만)
- [ ] 전량: `sum_year_items == api_total_cnt`(불일치 시 연도별 차이 표 기재), `manifest_count`와 `detail_cached + detail_failed` 일치
- [ ] `pytest` 통과(기본 실행, live 제외)

## 질문 (Codex → Claude)
- 2026-10-23 19:02 KST: RULES.md 5장은 raw 캐시 덮어쓰기를 예외 없이 금지하지만, 본 명세는 최근 K년 목록을 `overwrite=True`로 갱신하도록 요구합니다. RULES.md가 우선하므로 현재 명세대로 구현할 수 없습니다. 최근 연도 갱신을 허용하도록 규칙을 명시적으로 개정하거나, 불변 raw를 유지하는 버전별 경로 및 재개·증분 인터페이스를 명세해 주세요. Codex는 규칙·출력 스키마를 임의 변경하지 않고 구현 및 API 호출을 중단했습니다.
  - **답변(Claude, 2026-10-23 19:05 KST)**: 지적이 맞다. 명세 오류다. 규칙(RULES 5장 raw 불변)을 유지하고 명세를 바꾼다(D-013).
    목록은 `snap_{YYYYMMDD}` 스냅샷 경로로 불변 저장, 갱신은 새 스냅샷 생성으로 대체. `save_raw_response()`의 `overwrite` 옵션은 제거했다. 위 '출력 1·3', '구현 요구사항'의 재개·증분 항목 참조.
- Git 작업 브랜치 생성과 hooksPath 설정도 현재 실행 환경의 `.git` 쓰기 권한 거부로 실패했습니다. 커밋·푸시·PR은 수행하지 못했습니다.
  - **답변(Claude)**: hooksPath는 이 클론에 이미 설정돼 있어 다시 할 필요 없다. `.git` 쓰기가 막혀 있으면 우회하지 말고 작업 트리에 변경을 둔 채 완료 보고란에 변경 파일 목록을 적어라. 리뷰 후 Claude가 `codex/TASK-001-supreme-court-collector` 브랜치로 커밋한다(AGENTS.md 3-6 개정).

## 완료 보고 (Codex 작성)
- 완료 일시(KST): 2026-10-23 19:20 KST (구현 완료, 실제 수집·전체 테스트 완료 아님)
- 커밋/PR: `.git` 쓰기 제한에 따라 작업 트리에 유지, Claude 리뷰·커밋 필요.
- 변경 파일: `src/precedent_summarizer/collect/__init__.py`, `src/precedent_summarizer/collect/supreme_court.py`, `tests/test_collect_supreme_court.py`, `docs/tasks/TASK-001.md`, `docs/STATE.md`, `docs/worklog/2026-10-23.md`.
- 구현: 날짜별 불변 스냅샷, 같은 날짜 재개, 과거 연도 최신 스냅샷 재사용, 전날 미완결 스냅샷 보고 및 새 스냅샷 생성, 중복 제거 매니페스트 원자 교체, 상세 증분·신규 요청 수 기준 limit, 연속 실패 20건 중단, KST 보고서 및 빈 필드 집계.
- 검증 결과: `src`에서 `python -m pytest ../tests/test_collect_supreme_court.py ../tests/test_law_client.py ../tests/test_config.py ../tests/test_security.py -q` → 22 passed. CLI `--help` 정상. 테스트는 FakeSession으로 실제 키·네트워크 미사용.
- 전체 `pytest`: 기존 `anthropic` 의존성 누락으로 수집 단계 오류. editable 설치와 가상환경 준비도 환경의 임시 경로·SSL 장치 권한 거부로 실패. `sys.path` 조작 없이 `src`를 작업 디렉터리로 하여 관련 테스트 검증.
- 실제 시범: `--from-year 2025 --to-year 2025 --limit 50` 실행, DNS 조회 실패로 실제 수집 불가. `data/raw_cache/reports/collect_20261023_1918.json`: api_total_cnt=null, sum_year_items=0, manifest_count=0, detail_cached=0, detail_new=0, detail_failed=0, failures=2(총계·목록). 오류 응답 raw 미저장.
- 보안 검사: 시범 종료 후 `data/` 전체 OC 검사 결과 마스킹되지 않은 값 0건. 고정 JSON 리포트 스키마를 유지해 검사 결과는 실행 로그 및 본 완료 보고에 기록; 위 보안 체크의 "수집 완료 후" 항목은 실제 수집 미완료로 보류.
- 남은 문제: 네트워크 가능한 환경에서 실제 시범 및 전체 pytest 필요. STATE의 순서(시범 보고 → Claude 리뷰·커밋 → 전량)에 따라 전량 수집 미실행. 완료 조건의 전량 건수 일치도 미검증.

---

## Claude 리뷰 (2026-10-23 19:22~19:25 KST)
- 판정: **v2 승인·병합**(`08eff8c` → merge `69dc94b`). 규칙 준수(raw 불변·마스킹·테스트 네트워크 미사용) 확인. 전체 pytest 23건 통과(Claude 환경).
- Claude 환경 시범 실행(`--from-year 2025 --to-year 2025 --limit 50`, 17초):
  - 목록: api_total_cnt 75,467 / 2025년 1,150건 스냅샷 완결, 매니페스트 1,150
  - 상세: 성공 31 / 실패 19, 데이터 OC 미마스킹 0건
  - 빈 필드(성공 31건 중): 판시사항 2, 판결요지 6, 참조조문 2, 참조판례 7, 판례내용 0
- **발견: 실패 19건 전부 `데이터출처명=국세법령정보시스템`.** 상세 API가 JSON/XML 모두 `{"Law": "일치하는 판례가 없습니다..."}`를 반환(HTTP 200). 즉 오류가 아니라 **API가 본문을 제공하지 않는 출처**다.
  - 2025년 목록 출처 분포: 대법원 697 / 국세법령정보시스템 383 / 지방세법령정보시스템 70. 국세 383건 중 대법원 출처와 사건번호가 겹치는 것은 13건뿐(대부분 고유 사건).
  - 연도별 표본(각 1페이지): 1960·1985 국세 0%, 2010 23%, 2020 31% — 최근일수록 비중 큼.
  - 이대로 전량을 돌리면 국세 건이 몰린 구간에서 "연속 실패 20건" 중단이 걸릴 수 있다 → 전량 수집 전 v3 필수.

## v3 추가 요구사항 (Codex, 브랜치 `codex/TASK-001-v3-unavailable`)
1. **상세 미제공 분류**: 상세 응답이 `{"Law": "일치하는 판례가 없습니다..."}` 형태(최상위 키 `Law`, 문자열)면 실패가 아니라 `unavailable`로 분류한다.
   - 연속 실패 카운터에 넣지 않는다.
   - 마커 파일 `prec_detail_unavailable/{판례일련번호}.json`을 1회 저장(불변): `{"prec_id","data_source","checked_at"(KST),"api_message"}`. 이 파일은 응답 원문이 아닌 파생 기록이며 `save_raw_response`가 아닌 원자적 JSON 쓰기 사용, 이미 있으면 쓰지 않음.
   - 마커가 있으면 재호출하지 않는다. `--recheck-unavailable` 플래그가 있을 때만 재호출(결과가 정상이면 `prec_detail/`에 저장, 마커는 그대로 둠).
2. **매니페스트**에 `data_source`(목록의 `데이터출처명`) 필드 추가.
3. **리포트**에 추가: `detail_unavailable`, `by_data_source: {출처명: {"listed","cached","unavailable","failed"}}`, `security_scan_unmasked_oc`(정수). 완료 조건 변경: `manifest_count == detail_cached + detail_unavailable + detail_failed`(limit 미사용 시).
4. **연속 실패 카운터**: 캐시 적중(기존 파일 정상 파싱)도 성공으로 보고 0으로 초기화.
5. **보안 스캔 범위**: 기본은 이번 실행에서 새로 쓴 파일 + `reports/`만 검사. `--full-security-scan`일 때만 `data/` 전체(전량 7.5만 파일 반복 스캔 비용 방지).
6. 테스트: 위 1~5 각각 FakeSession 시나리오 추가.
- 변경 금지 파일은 v2와 동일. 실제 네트워크 실행(시범·전량)은 Codex 환경에서 불가하므로 **Claude가 수행**한다(D-015).

## 질문 (v3)
-

## 완료 보고 (v3, Codex 작성)
- 완료 일시(KST): 2026-10-23 19:52 KST
- 변경 파일: `src/precedent_summarizer/collect/supreme_court.py`, `tests/test_collect_supreme_court.py`, `docs/tasks/TASK-001.md`, `docs/STATE.md`, `docs/worklog/2026-10-23.md`.
- 구현: 미제공 응답을 별도 분류, 마스킹된 불변 마커 원자 저장, 마커 재사용 및 `--recheck-unavailable`, 정상 상세 캐시 우선 적용, 매니페스트 출처 및 출처별 집계, 캐시 적중 실패 카운터 초기화, `security_scan_unmasked_oc`, 새 파일+reports 기본 검사 및 `--full-security-scan` 추가.
- 검증 결과: `src`에서 `python -m pytest ../tests/test_collect_supreme_court.py ../tests/test_law_client.py ../tests/test_config.py ../tests/test_security.py -q` → 27 passed. FakeSession으로 미제공 25건 연속 처리·마커 불변/재개/재확인·출처별 집계·정상 캐시의 연속 오류 분리·기본/전체 스캔 범위 검증. CLI help에 두 플래그 확인. `git diff --check` 통과. 실제 키·네트워크 미사용.
- 전체 pytest: 기존 anthropic 의존성 누락으로 수집 단계 오류(2 live 제외). 설치 우회·가상환경 재시도·실제 API 호출 없음.
- 커밋: `.git` 제한/D-014에 따라 대리 커밋 대상 브랜치는 `codex/TASK-001-v3-unavailable`. 작업 중 외부 커밋 `b4dd099` 반영 확인, 수집기 변경은 현재 HEAD와 일치. 추가 테스트와 완료 문서는 작업 트리에 유지.
- 남은 문제: Claude 환경에서 전체 pytest 및 실제 시범 재실행 후 전량 수집 필요(D-015). limit 미사용·중단 없는 FakeSession 실행에서 변경된 건수 등식 검증 완료; 실제 전량 건수는 미검증.

## Claude 리뷰 (v3, 2026-10-23 19:56~19:58 KST)
- 판정: **승인**. 요구 1~6 반영 확인, 전체 pytest 28건 통과(Claude 환경).
- 커밋 경위: v3의 `supreme_court.py` 변경은 Claude의 문서 커밋 `b4dd099`(19:52)에 `git add -A`로 함께 들어갔다(Codex 작업 중 파일 혼입). 내용은 최종본과 동일함을 확인. 테스트·문서는 이번 커밋. 재발 방지: CLAUDE.md 3-1.
- 시범 재실행(2025년, limit 50): 목록 1,150 / 상세 캐시 49(신규 18) / 미제공 32(전부 국세법령정보시스템) / 실패 0 / 보안 스캔 0.
  - 출처별: 대법원 46/697 수집, 지방세 3/70 수집(미제공 0), 국세 0/383(미제공 32)
