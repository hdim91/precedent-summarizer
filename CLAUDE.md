# CLAUDE.md — Claude 작업 지침

규칙 원본은 **`docs/RULES.md`** 다. 이 파일은 Claude용 요약이며, 충돌 시 RULES.md가 우선한다.

## 0. 절대 규칙 (RULES.md 1장 요약)
- `.env`, `.env.*`(`.env.example` 제외)를 열람·출력·검색하지 않는다. 키는 존재 여부만 확인한다.
- 환경변수 값, 요청 URL의 `OC=` 값, API 헤더를 출력·기록하지 않는다. 로그 전 `mask_secrets()` 필수.
- 키 값을 채팅·문서·커밋·외부 자료(프로젝트 문서, 아티팩트, 메모리 포함)에 쓰지 않는다.
- `git add -f`, `--no-verify` 금지.

## 1. 세션 시작 시 읽는 순서
1. `docs/RULES.md` → 2. `docs/INTENT.md` → 3. `docs/STATE.md` → 4. `docs/worklog/` 최신 파일 → (필요 시) `docs/DECISIONS.md`

## 2. 담당 범위
- 아키텍처, 스키마·인터페이스(`src/precedent_summarizer/schemas/`), 요약 엔진(`engine/`, `prompts/`), 근거 검증기, 품질 평가
- 규칙·의도·결정 문서 관리, Codex 작업 명세(`docs/tasks/TASK-xxx.md`) 작성, Codex PR 리뷰·병합

## 3. Codex에 넘길 때
- `docs/tasks/_TEMPLATE.md`로 명세 작성 → 입출력 스키마·완료 조건·변경 금지 파일을 명시
- 배정 시각·회수 시각을 worklog에 기록
- 리뷰 체크: 비밀정보 노출(로그·예외·캐시), 기존 코드 재사용 여부, 빈 필드 임의 보완 여부, 테스트의 네트워크 사용 여부

## 4. 세션 종료 시
`docs/STATE.md` 덮어쓰기 → `docs/worklog/` 추가 → 결정 시 `docs/DECISIONS.md` 추가 → 커밋·푸시

## 5. 사용자 선호
- 답변은 전문가 수준, 아첨 없이. 시각은 KST로 명시.
- 최초 실행 작업은 double check. 재사용 가능한 코드 우선.
- 새 외부 API가 필요하면 로컬 확인 → 온라인 탐색 → 확보 여부를 사용자에게 질문.
