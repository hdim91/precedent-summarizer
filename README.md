# precedent-summarizer

대법원 판례를 수집(law.go.kr Open API)·요약(Claude API, 배치)해 내부용 웹으로 조회하는 프로그램.

- 범위: 대법원 판례 / 내부 연구용 / 배치 적재 방식
- 분업: 설계·요약 엔진·검증 = Claude, 반복·저비중 구현(판례 수집 등) = Codex

## 시작하기
1. `.env.example`을 복사해 `.env`로 저장하고 필수 키(`ANTHROPIC_API_KEY`, `LAW_API_KEY`) 입력
2. `.env`는 `.gitignore`로 커밋 제외됨

## 처음 클론한 경우
```bash
git config core.hooksPath scripts/hooks   # 비밀정보 커밋 차단 hook 활성화
```

## 문서 지도
| 문서 | 용도 |
|---|---|
| `docs/RULES.md` | 작업 규칙 단일 원본(보안·연속성·분업·코드·데이터·git·시간기록) |
| `docs/INTENT.md` | 프로젝트 목적·범위·설계 원칙 |
| `docs/STATE.md` | 현재 단계·다음 작업·미결정 |
| `docs/DECISIONS.md` | 결정 기록(추가 전용) |
| `docs/worklog/` | 일자별 작업로그(KST) |
| `docs/tasks/` | Codex 작업 명세 |
| `AGENTS.md` / `CLAUDE.md` | 에이전트별 지침(RULES.md 요약) |
