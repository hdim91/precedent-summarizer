# TASK-003: 웹 화면 (목록·검색 / 상세·근거 하이라이트)

- 작성: Claude · 작성일시: 2026-10-24 20:40 KST
- 담당: Codex · 브랜치: `codex/TASK-003-web-ui`
- 상태: 대기

## 목표
내부 연구자용 웹 화면 2개를 만든다. 데이터는 Claude가 만든 JSON API만 사용한다(서버 로직·SQL 추가 금지).

## 배경 / 관련 결정
- D-009(FastAPI + Jinja2/HTMX), INTENT(내부용·근거 기반 요약), D-022(DB 읽기 전용)
- 실행: `uvicorn precedent_summarizer.web.app:app --host 127.0.0.1 --port 8000` → API 문서 `/api/docs`

## 입력 (API — 변경 금지, 필요 시 "질문"란)
- `GET /api/stats` → `{precedents:{상태:건수}, by_source:{...}, summaries:[{version,model,n}]}`
- `GET /api/precedents?q=&year_from=&year_to=&case_type=&data_source=&has_summary=&version=v1|v1o&page=&size=`
  → `{total,page,size,items:[{prec_id,case_no,case_name,decision_date,decision_date_inferred,case_type_name,data_source,detail_status,summary_model,one_line}]}`
- `GET /api/precedents/{id}` → 메타, `holdings_clean`, `official_summary_clean`, `ref_statutes_clean`, `ref_precedents_clean`, `full_text_clean`, `sections:[{header,header_norm,start,end}]`, `summaries:[{version,model,verify_passed,created_at}]`
- `GET /api/precedents/{id}/summary/{version}` → `{summary, verify, evidence_spans:[{path,quote,start,end}]}` (start/end는 `full_text_clean`의 문자 오프셋, 못 찾으면 null)
- 요약 구조: `src/precedent_summarizer/schemas/summary.py`

## 출력
- `src/precedent_summarizer/web/templates/` — `base.html`, `index.html`, `detail.html` (현재 임시 파일 교체)
- `src/precedent_summarizer/web/static/` — `app.css`, `app.js`(필요 시). 외부 CDN은 htmx 1개만 허용(버전 고정, 예: `htmx.org@1.9.12`), 그 외 라이브러리 금지.

## 디자인 (Codex 재량, 사용자 지시 2026-10-24 20:22)
- 시각 디자인(레이아웃 세부, 색·타이포그래피, 컴포넌트 모양, 여백, 상호작용 연출)은 Codex가 정한다. 아래 '화면 요구사항'은 기능·정보 요건이며 배치·모양을 강제하지 않는다.
- 방향: 법률 문서를 오래 읽는 연구자용 — 긴 본문 가독성(줄 길이·줄간격), 요약과 원문 근거 대응이 한눈에 보일 것, 장식보다 정보 밀도.
- 완료 보고에 디자인 의도(3~5줄)와 주요 화면 설명을 적는다.

## 화면 요구사항
1. **목록·검색(`/`)**
   - 상단: 검색창(판례 전문 검색 — 3자 이상 단어는 전문검색, 짧으면 사건명·사건번호 검색이라는 안내 문구), 필터(선고연도 from~to, 사건종류, 출처, 요약 있음/없음, 요약 버전 v1/v1o).
   - 표: 선고일(추정 선고일이면 `추정` 배지), 사건번호, 사건명, 사건종류, 출처, 요약 상태(모델명 배지 Sonnet/Opus), 한 줄 요약(`one_line`).
   - `detail_status`가 `unavailable`이면 "본문 미제공(국세법령정보시스템)" 회색 표시.
   - 페이지네이션(20건). 필터·검색어·페이지는 URL 쿼리에 반영(새로고침·공유 시 유지).
   - 상단 요약 통계(`/api/stats`): 전체 판례 수, 본문 보유 수, 요약 수(버전·모델별).
2. **상세(`/precedents/{id}`)**: 2단 레이아웃(좌: 요약, 우: 판결 원문). 좁은 화면(≤900px)에서는 세로 배치.
   - 요약 버전 탭(v1 블라인드 / v1o 판결요지 참고) — 있는 버전만 표시. 없으면 "요약 없음".
   - 요약 패널: 한 줄 요약, 결론(유형 배지 + 문장), 쟁점별 판단(쟁점 → 결론 → 이유), 사실관계, 원심 판단(null이면 생략), 인용 조문·판례, 소수의견(있을 때), `not_in_text`("원문에 없는 정보"), 검증 결과(통과/인용 n/n/주문 대조 결과)와 모델명.
   - **근거 연결(핵심)**: 각 항목 옆 근거 표시(예: ①②)를 누르면 우측 원문의 해당 구간(`evidence_spans`의 start~end)이 하이라이트되고 그 위치로 스크롤. 원문을 렌더링할 때 `full_text_clean`을 **문자 오프셋 그대로** 사용해야 하므로, 하이라이트는 텍스트 노드 분할로 처리하고 HTML로 재해석하지 말 것(원문은 반드시 이스케이프). span이 null인 근거는 "원문 위치 미확인" 표시.
   - 원문 패널: 구획(`sections`) 목차 링크(【주문】【이유】 등), 줄바꿈 유지.
   - 하단 접기 영역: 판시사항, 판결요지(법원 작성), 참조조문, 참조판례 — "법원 작성 원문" 라벨.
   - 메타: 사건번호·사건명·법원·선고일(추정 여부)·사건종류·출처, law.go.kr 원문 링크 없이(키가 필요한 API 링크 금지).
3. **공통**: 한국어 UI, 시스템 폰트, 다크모드(prefers-color-scheme) 지원, 키보드 접근 가능(근거 버튼은 `<button>`), 법률 자문 아님 고지 문구(푸터: "연구용 자동 요약 — 원문을 확인하세요").

## 재사용할 기존 코드
- `web/app.py`의 라우트(`/`, `/precedents/{id}`)는 이미 템플릿을 렌더링함. 템플릿 컨텍스트는 `request`, `prec_id`뿐 — 데이터는 브라우저에서 API 호출(fetch 또는 htmx)로 가져온다.

## 변경 금지
- `src/precedent_summarizer/web/app.py`, `web/highlight.py`, `engine/`, `schemas/`, `load/`, `collect/`, `clients/`, `common/`, `docs/RULES.md`·`INTENT.md`·`DECISIONS.md`, `scripts/hooks/`

## 보안 체크
- [ ] 원문·요약 문자열은 전부 이스케이프(`textContent` 사용, `innerHTML`에 데이터 삽입 금지)
- [ ] 외부 요청은 htmx CDN 1개뿐, API 키·환경값 노출 없음

## 완료 조건
- [ ] `tests/test_web_templates.py`: TestClient로 `/`, `/precedents/1` 200 응답, 필수 요소(검색창·필터·요약/원문 패널 컨테이너·푸터 고지) 존재 확인(tmp DB, `tests/test_web.py`의 `make_db` 재사용 가능)
- [ ] 하이라이트 로직을 JS 순수 함수로 분리(`splitByRanges(text, ranges)`)하고, 같은 입력에 대한 기대 출력 예시를 주석으로 명시
- [ ] `pytest` 통과
- [ ] 실제 화면 확인은 사용자 PC에서(Claude가 스크린샷 검토)

## 질문 (Codex → Claude)
-

## 완료 보고 (Codex 작성)
- 완료 일시(KST):
- 변경 파일:
- 검증 결과:
- 남은 문제:
