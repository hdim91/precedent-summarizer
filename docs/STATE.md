# STATE — 현재 상태 (세션마다 덮어써서 최신화, 80줄 이하)

마지막 갱신: 2026-10-23 19:25 KST · 갱신자: Claude

## 현재 단계
**P1 수집 — TASK-001 v2 병합(69dc94b), v3(상세 미제공 출처 처리) Codex 배정 대기**

## 완료
- P0 전체(저장소·규칙·보안 hook·패키지 골격·클라이언트·키 검증) — 상세는 worklog
- TASK-001 v2: 수집기 구현(Codex) → Claude 리뷰·병합, 테스트 23건 통과
- 시범(2025년, limit 50, Claude 환경): 목록 1,150 완결, 상세 31 성공 / 19 실패(전부 국세법령정보시스템 출처)

## 차단 요인
- 전량 수집은 v3 반영 전까지 보류(국세 출처 연속 실패로 중단 위험)

## 다음 작업
1. Codex: TASK-001 v3(`docs/tasks/TASK-001.md` 하단)
2. Claude: v3 리뷰 → 시범 재실행 → 전량 수집 실행(D-015)
3. Claude: TASK-002(P2 정제·적재) 명세
4. Claude: P3 요약 출력 스키마·프롬프트 초안

## 미결정 (사용자)
- 상세 API 미제공 출처(국세·지방세, 최근 연도 20~33%)의 본문 확보: (a) 메타만 보관·요약 제외 (b) law.go.kr 웹 화면(`LSW/precInfoP.do`)에서 수집 (c) 다른 출처 탐색

## 운영 방식
- Codex: 코드·가짜 응답 테스트까지(네트워크·venv 불가). 실제 API 실행은 Claude(D-015). git 커밋은 Claude 대리(D-014)

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
