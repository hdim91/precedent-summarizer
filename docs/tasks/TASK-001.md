# TASK-001: 대법원 판례 전량 수집 (목록 + 상세 → raw 캐시)

- 작성: Claude · 작성일시: 2026-10-23 18:48 KST
- 담당: Codex · 브랜치: `codex/TASK-001-supreme-court-collector`
- 상태: 대기

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
- 실행 인자(CLI): `--from-year`(기본 1947), `--to-year`(기본 올해), `--stage {list,detail,all}`, `--limit N`(시범용), `--refresh-recent-years K`(기본 1: 최근 K년 구간은 목록을 다시 받아 신규분 확인)

## 출력 (스키마 고정 — 변경 시 "질문"란에 기재 후 중단)
경로 기준: `Settings.raw_cache_dir`(기본 `data/raw_cache/`)
1. 목록 raw: `prec_list/org400201/{YYYY}/p{page:04d}.json` — **선고연도 단위로 구간 분할**(페이지 밀림 방지)
2. 상세 raw: `prec_detail/{판례일련번호}.json`
3. 매니페스트: `manifest/prec_ids_org400201.jsonl` — 한 줄 1건 `{"prec_id","case_no","decision_date","year","list_file"}` (목록에서 추출, 중복 제거)
4. 수집 리포트: `reports/collect_{YYYYMMDD_HHMM}.json` —
   `{"run_started","run_finished","api_total_cnt","year_slices":[{"year","total_cnt","pages","items"}],"sum_year_items","manifest_count","detail_cached","detail_new","detail_failed","failures":[{"prec_id","stage","error"}],"empty_field_counts":{"판시사항":n,...}}`
   - 시각은 KST ISO8601. `error`는 `MaskedRequestError` 메시지(이미 마스킹됨)만.

## 구현 요구사항
- 모듈: `src/precedent_summarizer/collect/supreme_court.py`, CLI: `python -m precedent_summarizer.collect.supreme_court`
- 연도 구간별 1페이지 호출로 `totalCnt`를 얻고 `ceil(totalCnt/100)`페이지 순회.
- **재개**: 이미 존재하는 raw 파일은 재호출하지 않는다(`save_raw_response` 기본 불변). 단, `--refresh-recent-years` 구간의 목록 파일은 `overwrite=True`로 갱신.
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
- [ ] `.env` 미열람, 키 값 미출력
- [ ] 로그·예외 출력은 마스킹 경유(`install_log_masking`, `MaskedRequestError`)
- [ ] raw 저장은 `save_raw_response`만 사용(직접 `write_bytes(resp.content)` 금지)
- [ ] 테스트에서 실제 키·네트워크 미사용(FakeSession 사용 — `tests/test_law_client.py` 참고)
- [ ] 수집 완료 후 `data/` 전체에서 `[?&]OC=` 뒤에 `***` 아닌 값이 없는지 검사 결과를 리포트에 포함

## 완료 조건
- [ ] 단위 테스트(`tests/test_collect_supreme_court.py`): 페이지 계산, 재개(기존 파일 스킵), 비정상 응답 미저장, 매니페스트 중복 제거, 리포트 스키마
- [ ] 시범: `--from-year 2025 --to-year 2025 --limit 50` 실행 → 리포트 첨부(건수만)
- [ ] 전량: `sum_year_items == api_total_cnt`(불일치 시 연도별 차이 표 기재), `manifest_count`와 `detail_cached + detail_failed` 일치
- [ ] `pytest` 통과(기본 실행, live 제외)

## 질문 (Codex → Claude)
-

## 완료 보고 (Codex 작성)
- 완료 일시(KST):
- 커밋/PR:
- 검증 결과:
- 남은 문제:
