# 안전 규칙 (safety-rules)

> **목적:** 재무 데이터를 다룰 때 결과를 틀리게 하거나 신뢰할 수 없게 만드는 것을 막는 **하드 규칙**과 그 근거·적용법. CLAUDE.md의 "절대 규칙"의 상세판이다.

## 1. 회사별 하드코딩 금지
- **금지:** 회사명·`corp_code`·종목코드·계정별 특수 분기를 코드에 삽입.
- **근거:** 다음 입력에서 깨지고, 한 표본 회사에 과적합된다.
- **적용:** 그런 값은 데이터·`config/settings.yaml`·`mappings/`에서 온다. 산업/회사와 무관하게 **동일한 코드 경로**를 쓴다.

## 2. 원본(raw) 보호 — append-only
- **금지:** `data/raw/` 안 API 스냅샷의 편집·덮어쓰기.
- **근거:** raw는 감사·재현의 기준선이다.
- **적용:** `parsed`는 언제나 raw에서 재생성 가능해야 한다. raw는 verbatim + `sha256` + manifest로 남긴다.

## 3. 조용한 데이터 손실 금지
- **금지:** 버려진 행·누락 계정·실패 호출·계산불가 비율을 말없이 제거.
- **적용:** 모두 기록·표면화한다(missing-manifest, 로그, 라벨). dedup은 **결정적**으로 하고 살아남은 `rcept_no`를 기록한다.
- **불확실한 계정 매핑**은 임의 fuzzy matching으로 확장하지 않는다. 확정 불가 시 `NOT_COMPUTABLE` + `reason=mapping_not_confident`로 남긴다(조용한 추정 금지).

## 4. 단위·부호 무결성
- **적용:** 금액은 full-value `Decimal`로 verbatim 저장(수집 시 재스케일 금지). 정규화가 필요하면 **명시적·로그가 남는** 다운스트림 단계에서만. 분자·분모 `currency`/`unit` 불일치 시 나눗셈하지 않는다.

## 5. 소스 추적성(traceability)
- **적용:** 모든 출력값은 `rcept_no` / `account_id` / `bsns_year` / `retrieved_at`로 원본 filing까지 역추적 가능해야 한다. 벤치마크는 `peer_corp_codes`로 풀 구성원을 드러낸다.

## 6. 재현성(reproducibility)
- **적용:** **캐시 우선** 수집(`request_hash` = endpoint + 정렬된 파라미터(키 제외) 해시). 같은 입력 → 같은 출력. 실행 파라미터·타임스탬프를 남긴다. 무작위성·순서 의존 금지.

## 7. API 키 취급
- **금지:** 키를 코드/설정/리포에 넣기.
- **적용:** 키는 `.env`의 `OPENDART_API_KEY`에서만 읽는다. 없으면 **즉시 중단**(조용히 진행 금지). `.env`는 gitignore.

## 8. 출력 파일 안전
- **적용:** 타임스탬프 파일명 + `os.path.exists` 확인. 기존 파일은 `--overwrite` 없이 덮지 않는다. 임시 파일 → 원자적 교체로 손상 방지.

## 9. 승인·파괴적 명령
- **적용:** `docs/` 계획 승인 전 비즈니스 로직 미구현. 대량 삭제·강제 덮어쓰기 등 파괴적 명령은 사전 확인.

## 10. 판정 표현·색상 무결성 (Loop 3)
- **금지:** HIGH/LOW를 좋음/나쁨·부정·오류·왜곡표시·위험의 **결론**으로 표기. 초록/빨강처럼 좋고 나쁨을 암시하는 색상.
- **근거:** 본 산출물은 감사 보조용 **screening** 자료다. HIGH/LOW는 **산업 대비 상대적 위치**(높음/낮음)일 뿐이다.
- **적용:** HIGH=주황 계열, LOW=파랑 계열, NORMAL=무색/연회색, 계산불가/peer부족/분포부족=회색 계열. 감사 관점 코멘트는 "검토 후보/추가 확인 필요/산업 대비 상대적 위치"로만 표현하고 과장 문구를 쓰지 않는다. 이 한계를 Excel 00_README/07_Methodology에 명시한다.

## 11. benchmark mapping 엄격성 (Loop 3)
- **적용:** 매출채권·매입채무는 순수 계정 기준을 유지하고 `및기타채권/및기타채무` fallback을 Loop 3 기본 benchmark에 추가하지 않는다. 재고자산 nm-fallback도 확장하지 않는다. 불확실 매핑은 `NOT_COMPUTABLE` + `reason=mapping_not_confident`. 삼성전자 결과를 맞추기 위한 예외처리·회사별 hardcoding 금지.

## 12. 판정 과장/과소 해석 방지 (Loop 3-B)
- **금지 표현:** "위험 없음 / 문제 없음 / 검토 불필요 / 부정 없음 / 오류 없음 / 왜곡표시 없음". NORMAL을 안전 확정처럼 쓰지 않는다.
- **적용:** NORMAL = "현재 peer universe·IQR fence 기준상 이상치 아님"으로만 표현. deviation_rate(비율차이%)는 %p 차이·percentile·robust_z·benchmark_quality와 **함께** 제시해 단독 과장 해석을 막는다. median이 작아 배수차이가 크게 보이는 경우 비고를 남긴다. 표현/비고/방법론만 보완하고 계산·label은 변경하지 않는다.
