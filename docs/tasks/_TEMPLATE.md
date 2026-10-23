# TASK-xxx: <작업명>

- 작성: Claude · 작성일시: YYYY-MM-DD HH:MM KST
- 담당: Codex · 브랜치: `codex/TASK-xxx-<짧은설명>`
- 상태: 대기 | 진행 | 질문 | 완료 | 반려

## 목표
<한두 문장>

## 배경 / 관련 결정
- 관련 DECISIONS: D-xxx

## 입력
- <파일·API·파라미터>

## 출력 (스키마 고정 — 변경 시 "질문"란에 기재 후 중단)
- <경로·형식·필드>

## 재사용할 기존 코드
- <모듈·함수>

## 변경 금지
- `docs/RULES.md`, `docs/INTENT.md`, `docs/DECISIONS.md`, `schemas/`, `engine/`, `prompts/`, `scripts/hooks/`
- <추가 항목>

## 보안 체크 (RULES.md 1장)
- [ ] `.env` 미열람, 키 값 미출력
- [ ] 로그·예외 출력은 `mask_secrets()` 경유
- [ ] raw 캐시에 요청 URL·헤더 미저장
- [ ] 테스트에서 실제 키·네트워크 미사용

## 완료 조건
- [ ] <검증 가능한 조건>
- [ ] `pytest` 통과

## 질문 (Codex → Claude)
-

## 완료 보고 (Codex 작성)
- 완료 일시(KST):
- 커밋/PR:
- 검증 결과:
- 남은 문제:
