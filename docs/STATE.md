# STATE — 현재 상태 (세션마다 덮어써서 최신화, 80줄 이하)

마지막 갱신: 2026-10-23 18:57 KST · 갱신자: Claude

## 현재 단계
**P0 환경 구축 — 완료** → **P1 수집: TASK-001 Codex 배정 대기**

## 완료 (P0)
- 저장소 `C:\Users\hdim9\code\precedent-summarizer` ↔ GitHub private
- 규칙·연속성 문서, AGENTS.md/CLAUDE.md, pre-commit 비밀유출 차단 hook
- 패키지 골격: `config`, `common/security`(마스킹), `clients/law_go_kr`(HTTPS·예외 마스킹·raw 불변 저장), `schemas/precedent.py`, `schemas/db.sql`
- `clients/anthropic_client.py`(단일 진입점, 조직 범위 키용 워크스페이스 헤더 선택 지원)
- `scripts/check_env.py`(존재 여부만), 테스트 14건 + live 2건 통과
- OneDrive 원본 코드 키 노출 수정 및 기존 캐시 마스킹(D-011)

## 차단 요인
- 없음. Anthropic 키(워크스페이스 범위) 검증 완료: `claude-sonnet-5-5`·`claude-opus-5-5` 조회 및 Messages 호출 정상(18:56)

## 다음 작업
1. TASK-001 Codex 배정(사용자가 Codex에 `docs/tasks/TASK-001.md` 전달) → 시범(2025년, 50건) 보고 → 전량
2. Claude: TASK-002(P2 정제·적재) 명세 작성 — TASK-001 시범 결과로 필드 공백률 확인 후
3. Claude: P3 요약 출력 스키마·프롬프트 초안

## 미결정
- 없음 (모델 ID는 P3 시범 후 확정)

## 알려진 리스크
- 전량 상세 수집 75,467회 호출 → 0.1s 간격·응답시간 고려 시 장시간(수 시간~하루). 재개 가능 설계로 대응
- 전량 요약 비용 큼 → P3 시범 실측 후 예산 승인(BATCH_BUDGET_USD) 게이트
- OneDrive 버전 기록에 마스킹 전 캐시가 남아 있음 — OneDrive 폴더를 외부와 공유 중이면 LAW_API_KEY 재발급 권장

## 실행 방법 (Windows)
```
python -m venv .venv && .venv\Scripts\activate
pip install -e ".[dev]"
python scripts\check_env.py
pytest            # live 제외
pytest -m live    # 실제 API (키 필요)
```
