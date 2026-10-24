# STATE — 현재 상태 (세션마다 덮어써서 최신화, 80줄 이하)

마지막 갱신: 2026-10-24 23:41 KST · 갱신자: Codex

## 현재 단계
**P1·P2 완료**(DB 75,467행) · TASK-002b Codex 진행 중 · **P3 모델 (C) 확정** · **P4 배치 모듈 완성(드라이런만, 미제출)** — 입력 변형(blind/official) 결정 대기

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

## 차단 요인
- v4 실제 undated 수집·총계 검증은 Claude/사용자 환경에서 진행 필요.
- Codex 환경 전체 pytest는 anthropic 미설치로 차단, TASK-002b 포함 관련 테스트 76건 통과.

## 다음 작업
- TASK-003c 리뷰·커밋 후 1440×960 목록 5행/요약 없는 상세·근거/배지 화면 재검토.
- TASK-003b 리뷰·커밋 후 PC 스크린샷(목록/상세/미니맵·모바일/다크/인쇄) 검토.
- TASK-003 리뷰·커밋 후 PC에서 웹 화면/근거 스크롤·모바일·다크모드 확인.
1. 사용자: 입력 변형 평가 방식 승인(아래 '미결정')
2. Codex: TASK-002b → Claude 리뷰 → 사용자 PC 재적재(심리불속행·추정 선고일 반영 후 선정)
3. Claude/사용자: 평가 배치 → 본 배치(PC에서 `python -m precedent_summarizer.engine.batch submit ...`)

## 미결정 (사용자)
- 판시사항·판결요지 입력 여부: (가) 평가용 60~120건만 두 버전 → 채점 후 결정(추가 약 $5~11) (나) 전량 두 버전(처리량 절반, 1,233건)
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
