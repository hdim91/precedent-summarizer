# DECISIONS — 결정 기록 (추가만, 수정 금지. 번복은 새 항목으로)

| ID | 일시(KST) | 결정 | 근거/비고 |
|---|---|---|---|
| D-001 | 2026-10-23 13:08 | 엔진은 Claude API, 주요 코딩은 Claude, 일부 코딩은 Codex | 사용자 지시 |
| D-002 | 2026-10-23 13:12 | 반복·저비중 코딩(판례 수집 포함)은 Codex 담당 | 사용자 지시 |
| D-003 | 2026-10-23 13:14 | 내부 연구용 / 배치 적재 방식 / 대법원만 / git 관리 | 사용자 결정 |
| D-004 | 2026-10-23 13:14 | 판례 원문 소스는 law.go.kr Open API(`target=prec`) | 기존 키·코드 보유 |
| D-005 | 2026-10-23 13:14 | 저장소: SQLite 단일 파일 + FTS5(trigram) | 내부용·배치 규모에 충분, OneDrive 다수 파일 회피 |
| D-006 | 2026-10-23 13:18 | 저장소 위치 A안: OneDrive 밖 `C:\Users\hdim9\code\precedent-summarizer` + GitHub private | OneDrive와 `.git` 충돌 위험 |
| D-007 | 2026-10-23 18:38 | 규칙 단일 원본 `docs/RULES.md`, 컨텍스트 연속성은 INTENT/STATE/worklog/DECISIONS 4종 문서로 관리 | 세션 단절·에이전트 간 인수인계 대비 |
| D-008 | 2026-10-23 18:38 | 비밀정보: `.env` 열람 금지, 존재 여부만 확인, pre-commit hook으로 기계 차단, OC 키 URL 마스킹 의무 | law.go.kr은 키를 URL 파라미터로 전송 |
