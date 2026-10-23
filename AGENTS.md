# AGENTS.md — Codex 작업 지침

이 저장소의 규칙 원본은 **`docs/RULES.md`** 다. 이 파일은 Codex용 요약이며, 충돌 시 RULES.md가 우선한다.

## 0. 절대 규칙 (RULES.md 1장 요약 — 반드시 준수)
- `.env`, `.env.*`(`.env.example` 제외)를 **열지도, 출력하지도, 검색하지도 않는다.**
- 환경변수 값을 출력하지 않는다(`env`, `printenv`, `echo $VAR`, `print(os.environ)` 금지). 존재 여부만 `bool()`로 확인.
- 키 값을 코드·테스트·로그·커밋·PR·문서에 쓰지 않는다. 예시는 `<YOUR_KEY>` 자리표시자만.
- law.go.kr 요청 URL·예외 메시지는 `OC=` 키를 포함하므로 **반드시 `mask_secrets()`를 거쳐** 로그에 남긴다. raw 캐시에는 응답 본문만 저장.
- `git add -f`, `git commit --no-verify` 금지. 테스트는 실제 키·네트워크 사용 금지(`@pytest.mark.live`만 예외, 기본 제외).

## 1. 세션 시작 시 읽는 순서
1. `docs/RULES.md` → 2. `docs/INTENT.md` → 3. `docs/STATE.md` → 4. `docs/worklog/` 최신 파일 → 5. 배정된 `docs/tasks/TASK-xxx.md`

## 2. 담당 범위
- 담당: 판례 수집(페이징·증분·재시도·캐시), 파싱·정제, DB 적재, 단순 CRUD, UI 화면, 단위 테스트
- **변경 금지(Claude 소유)**: `docs/RULES.md`, `docs/INTENT.md`, `docs/DECISIONS.md`, `src/precedent_summarizer/schemas/`, `src/precedent_summarizer/engine/`, `prompts/`, `scripts/hooks/`
- 명세에 없는 인터페이스 변경이 필요하면 구현하지 말고 명세 파일 "질문" 란에 적고 멈춘다.

## 3. 작업 절차
1. `docs/tasks/TASK-xxx.md`의 목표·입출력·완료 조건을 확인한다.
2. 브랜치 `codex/TASK-xxx-짧은설명`에서 작업한다. `main`에 직접 커밋하지 않는다.
3. 기존 코드(`LawGoKrClient` 등)를 확장한다. 같은 기능을 새로 만들지 않는다.
4. 완료 조건의 검증(테스트·건수 리포트)을 실행하고 결과를 명세 파일 "완료 보고" 란에 적는다.
5. `docs/worklog/YYYY-MM-DD.md`에 시각(KST)과 함께 한 일을 추가하고, `docs/STATE.md`의 해당 항목을 갱신한다.
6. 커밋·푸시 후 PR을 연다. 병합은 Claude 리뷰 후.

## 4. 환경
- Python 3.10+, 패키지 루트 `src/precedent_summarizer/`, 테스트 `tests/`(pytest)
- 최초 클론 후 1회: `git config core.hooksPath scripts/hooks`
