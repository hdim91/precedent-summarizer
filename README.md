# precedent-summarizer

대법원 판례를 수집(law.go.kr Open API)·요약(Claude API, 배치)해 내부용 웹으로 조회하는 프로그램.

- 범위: 대법원 판례 / 내부 연구용 / 배치 적재 방식
- 분업: 설계·요약 엔진·검증 = Claude, 반복·저비중 구현(판례 수집 등) = Codex

## 시작하기
1. `.env.example`을 복사해 `.env`로 저장하고 필수 키(`ANTHROPIC_API_KEY`, `LAW_API_KEY`) 입력
2. `.env`는 `.gitignore`로 커밋 제외됨
