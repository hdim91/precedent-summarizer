# STATE — 현재 상태 (세션마다 덮어써서 최신화, 80줄 이하)

마지막 갱신: 2026-10-23 18:38 KST · 갱신자: Claude

## 현재 단계
**P0 환경 구축 — 진행 중**

## 완료
- 저장소 생성: `C:\Users\hdim9\code\precedent-summarizer` ↔ `github.com/hdim91/precedent-summarizer`(private)
- `.env.example` / `.gitignore` / README, 사용자 `.env` 키 입력 완료(값 미열람, 존재·무시 여부만 확인)
- 규칙·의도·상태·결정·작업로그 문서, `AGENTS.md`·`CLAUDE.md`, Codex 작업 명세 템플릿
- pre-commit 비밀유출 차단 hook

## 다음 작업 (P0 잔여, 담당 Claude)
1. `pyproject.toml`, `src/precedent_summarizer/` 패키지 골격
2. `LawGoKrClient` 이식 + `common/security.py`(`mask_secrets`) 구현, 예외 메시지 OC 마스킹, https 전환 검증
3. 키 존재 확인 스크립트(`scripts/check_env.py`, 값 비출력)
4. P1 수집 명세 `docs/tasks/TASK-001.md` 작성 → Codex 배정

## 미결정 (사용자 결정 필요)
- 웹 스택: FastAPI+Jinja2/HTMX(권장) vs Streamlit
- 수집 범위: 대법원 전체 vs 최근 N년 / 특정 법 분야부터

## 알려진 리스크
- 원본 `LawGoKrClient`(OneDrive CODE)는 예외 메시지에 OC 키가 포함된 URL이 그대로 남고, HTTP로 호출함 → 이 저장소 이식본에서 수정. 원본 수정 여부는 사용자 확인 필요.
- 모델 ID(`claude-sonnet-5-5`, `claude-opus-5-5`)는 잠정값 — P3 시범 후 확정.
