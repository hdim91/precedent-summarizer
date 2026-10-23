# STATE — 현재 상태 (세션마다 덮어써서 최신화, 80줄 이하)

마지막 갱신: 2026-10-23 21:24 KST · 갱신자: Codex

## 현재 단계
**P1 수집 — 목록 전 연도 완료(72,041), 상세 전량 수집 대기(사용자 Windows 실행), TASK-001 v4(undated) 구현·단위 검증 완료, Claude 리뷰 대기**

## 완료
- P0 전체(저장소·규칙·보안 hook·패키지 골격·클라이언트·키 검증) — 상세는 worklog
- TASK-001 v2: 수집기 구현(Codex) → Claude 리뷰·병합, 테스트 23건 통과
- TASK-001 v3: 미제공 마커·재확인·출처 집계·스캔 범위 구현, FakeSession 포함 관련 27건 통과
- 시범(2025년, limit 50, Claude 환경): 목록 1,150 완결, 상세 31 성공 / 19 실패(전부 국세법령정보시스템 출처)

- TASK-001 v4: undated 구간·date_status·null 연도 상세 필터·제외 플래그 구현, 관련 34건 통과

## 차단 요인
- v4 실제 undated 수집·총계 검증은 Claude/사용자 환경에서 진행 필요.
- Codex 환경 전체 pytest는 anthropic 미설치로 차단, 관련 테스트 34건 통과.

## 다음 작업
1. 사용자: Windows에서 상세 전량 수집 실행(재개 가능, 수 시간) — 명령은 아래 '실행 방법'
2. Claude: TASK-001 v4 리뷰·대리 커밋 → 전체 pytest → undated 3,426건 추가 수집·총계 대조
3. Claude: TASK-002(P2 정제·적재) 명세, P3 요약 스키마·프롬프트 초안

## 미결정 (사용자)
- 국세 출처 본문: 현재 (a) 메타만 보관으로 진행(D-017). 대체 경로로 공공데이터 제공신청 여부 결정 필요 — `docs/notes/source_tax_precedents.md`

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
mkdir data\logs
python -m precedent_summarizer.collect.supreme_court --from-year 1947 2> data\logs\collect.log
```
- 중단돼도 같은 명령 재실행 시 이어서 수집(받은 파일은 건너뜀). 결과는 `data\raw_cache\reports\collect_*.json`
