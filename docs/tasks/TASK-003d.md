# TASK-003d: 웹 기본 요약 버전을 v1o로

- 작성: Claude · 작성일시: 2026-10-25 14:25 KST · 담당: Codex · 브랜치: `codex/TASK-003d-default-v1o` · 상태: 구현·자동 검증 완료, 화면 리뷰 대기
- 배경: D-024 — 본 배치는 v1o(판시사항·판결요지 참고). 판결요지 없는 판결은 v1만 존재.

## 요구사항
1. 목록 화면 '요약 버전' 필터 기본값을 `v1o`로, 선택지 순서도 v1o → v1. URL에 version이 없으면 v1o.
2. 목록에서 선택한 버전의 요약이 없고 다른 버전이 있으면, 요약 상태 칸에 다른 버전 배지를 흐리게 표시(예: `v1만 있음`). API 변경 없이 처리할 수 없으면 '질문'란에 기재.
3. 상세 화면 탭 순서·기본 선택: v1o 우선, 없으면 v1. 탭 라벨은 'v1o · 판결요지 참고(기본)', 'v1 · 블라인드(비교용)'.
4. 통계 카드 라벨도 같은 명칭.

## 제약·완료 조건
- TASK-003b/c 제약 동일(서버 코드 변경 금지, textContent만, 웹폰트 유지).
- 웹 테스트 갱신·통과, 완료 보고 작성.

## 질문 (Codex → Claude)
-

## 완료 보고 (Codex 작성)
- 완료 일시(KST): 2026-10-25 14:27 KST
- 변경 파일: `src/precedent_summarizer/web/static/app.js`, `app.css`, `src/precedent_summarizer/web/templates/index.html`, `tests/test_web_highlight.cjs`, `tests/test_web_templates.py`, `docs/tasks/TASK-003d.md`, `docs/STATE.md`, `docs/worklog/2026-10-25.md`.
- 처리: 목록 선택지 v1o→v1 및 URL version 미지정 시 v1o 명시 요청. 기본 필터 판정도 v1o로 변경. 상세 버전 탭은 v1o 우선·없으면 v1, 공통 라벨(통계 포함)은 “v1o · 판결요지 참고(기본)”/“v1 · 블라인드(비교용)”.
- 다른 버전 배지: 선택 버전 요약이 없는 행에만 기존 GET /api/precedents/{id}의 summaries 조회. 다른 버전만 있으면 점선·보조색 배지(v1만 있음/v1o만 있음). 최대 4개 동시 조회, ID별 메타 캐시로 페이지 이동 시 재사용, 검색 전환 시 이전 요청 중단. 추가 조회 실패는 “다른 버전 확인 불가”로 구분. 서버/API 변경 없음으로 요구 2 처리 가능, 추가 인터페이스 질문 없음.
- 검증 결과: TestClient+Node 웹 테스트 9 passed. 기본 선택지 순서·라벨, v1o 우선/단독 v1 fallback·빈 목록·다른 버전만 존재/둘 다 존재·API 배열 불변 검증. `python -m pytest ../tests --ignore=../tests/test_anthropic_client.py -q` → 106 passed, 2 deselected(live). 기존 anthropic 의존성 미설치 파일만 제외. Node 구문·기존 하이라이트/미니맵 테스트·git diff --check 통과.
- 남은 문제: 사용자 PC 화면 확인 및 의존성 설치 환경의 전체 pytest 필요. 실제 DB/API·네트워크 사용 없음. 서버/웹폰트 미변경. `.git` 읽기 전용으로 작업 트리에 유지, 리뷰 후 `codex/TASK-003d-default-v1o` 브랜치 커밋 필요.
