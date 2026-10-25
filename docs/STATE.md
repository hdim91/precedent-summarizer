# STATE — 현재 상태 (세션마다 덮어써서 최신화, 80줄 이하)

마지막 갱신: 2026-10-25 21:50 KST · 갱신자: Claude

## 현재 단계
**P4 배치 사실상 완료**: v1o 요약 약 3,530건(2026-08 → 2022년대, 최신순), 최종 재시도 62건 처리 대기(`msgbatch_012sTjbuABgJjwiAtvgaD7Wx`). 예산 상한 $85 도달 — 추가 submit 중단. 웹 완료(TASK-003~003d).

## 완료
- P0 전체(저장소·규칙·보안 hook·패키지 골격·클라이언트·키 검증) — 상세는 worklog
- TASK-001 v2: 수집기 구현(Codex) → Claude 리뷰·병합, 테스트 23건 통과
- TASK-001 v3: 미제공 마커·재확인·출처 집계·스캔 범위 구현, FakeSession 포함 관련 27건 통과
- 시범(2025년, limit 50, Claude 환경): 목록 1,150 완결, 상세 31 성공 / 19 실패(전부 국세법령정보시스템 출처)

- TASK-001 v4: undated 구간·date_status·null 연도 상세 필터·제외 플래그 구현, 관련 34건 통과

- TASK-002: 정규화·멱등 SQLite 적재·FTS·load_runs 구현, 관련 54건 통과(신규 20건)

- TASK-002b: 날짜 보강·심리불속행·v2 DB 호환·warnings 분리 구현, 관련 76건 통과. 실제 재적재 대기.

- TASK-003: 목록/검색·상세/근거 연결 UI 구현, 웹·JS 테스트 9건 통과. PC 화면 검토 대기.

- TASK-003b: 판례집/워크벤치 디자인·미니맵·모바일 카드·인쇄 구현, 웹9/회귀103 통과. 실제 화면 검토 대기.

- TASK-003c: 표시 순서 근거 번호·법원 요지 대체·목록 밀도·표제 결론 배지 수정, 웹9/회귀103 통과. PC 재검토 대기.

- TASK-003d: 기본 v1o·단독 v1 fallback·다른 버전 배지·라벨 통일, 웹9/회귀106 통과. 화면 리뷰 대기.

## 차단 요인
- v4 실제 undated 수집·총계 검증은 Claude/사용자 환경에서 진행 필요.
- Codex 환경 전체 pytest는 anthropic 미설치로 차단, TASK-002b 포함 관련 테스트 76건 통과.

## 다음 작업
1. 사용자(PC): 재시도 배치 `collect` → `spend`, 콘솔 잔액 확인
2. Claude: 최종 통계(총 요약 수, 사건종류별 통과율, 선고일 범위, 실패 사유 분포) — PC에서 내보낸 통계 파일 기반(D-022: 원격 셸은 DB 직접 접근 불가)
3. 개선 과제: 비용 추정을 모델·재시도 여부별로 분리 보정(Opus 재시도 과소추정 1.16배), 변호사 표본 검토
4. 추가 예산 확보 시: `submit --variant official`로 2022년 이전 판결 이어서

## 미결정 (사용자)
- 국세 출처 본문 공공데이터 제공신청 여부(D-017)

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
