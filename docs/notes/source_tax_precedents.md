# 국세 출처 판례 본문 확보 경로 탐색 (D-017)

갱신: 2026-10-23 19:52 KST · Claude

## 확인된 사실
- law.go.kr 판례 목록에서 `데이터출처명=국세법령정보시스템`인 판례는 본문 조회 API(`lawService.do?target=prec`)가 JSON·XML에서 `{"Law":"일치하는 판례가 없습니다..."}`를 반환한다(2026-10-23 실측).
- 공식 가이드(open.law.go.kr, 판례 본문 조회 API): **"국세청 판례 본문 조회는 HTML만 가능합니다."**
- 그러나 `type=HTML` 응답은 본문이 아니라 래퍼 페이지다. iframe·ajax로 `https://www.law.go.kr/LSW/precInfoP.do?precSeq={ID}&mode=0`을 불러오고, 이 페이지는 다시 국세법령정보시스템(taxlaw.nts.go.kr) 화면을 JavaScript로 렌더링한다. 단순 HTTP 요청으로는 본문 텍스트(주문·이유 등)가 나오지 않는다.
- 국세법령정보시스템에서 판례 Open API나 일괄 다운로드를 제공한다는 근거는 찾지 못했다. 공공데이터포털에는 법제처가 제공하는 국세청 법령해석, 조세심판원 재결례 API는 있으나 국세청 판례 본문 API는 없다.
- 지방세법령정보시스템 출처는 시범 50건 중 2건이 JSON 본문 조회에 성공 — 출처 전체가 막힌 것은 아님(전량 수집 후 비율 확인 필요).

## 남은 선택지
1. **공공데이터 제공신청**(공공데이터포털 → 국세청/법제처 대상): 공공데이터법에 따른 정식 경로. 처리 기간이 걸리지만 이용 조건이 명확해진다.
2. 브라우저 자동화로 taxlaw.nts.go.kr 화면 수집: 기술적으로 가능하나 공식 API가 아니고 이용약관 확인이 선행돼야 하며 구조 변경에 취약 — 현재 비권장.
3. 현행 유지: 메타만 보관, 요약 제외(D-017 (a)).

## 출처
- 판례 본문 조회 API 가이드: https://open.law.go.kr/LSO/openApi/guideResult.do?htmlName=precInfoGuide
- 법제처_조세심판원 행정심판 재결례 목록 조회: https://www.data.go.kr/data/15140320/openapi.do
- 법제처_국세청 법령해석 목록 조회: https://www.data.go.kr/data/15140313/openapi.do
