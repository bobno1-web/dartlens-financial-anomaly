# DESIGN_INVARIANTS — 위반 불가 설계 불변식

> **목적:** 어떤 루프에서도(조사·구현·리팩터·일반화 포함) **깨서는 안 되는** 설계 규칙.
> 하나라도 위반하면 검증방은 무조건 `FAIL`([`VALIDATION_ROOM.md`](./VALIDATION_ROOM.md) §4).
> 정본 근거: 루트 `CLAUDE.md`, `references/safety-rules.md`, `references/methodology.md`,
> `config/settings.yaml`. **이 파일이 그 정본과 모순되면 정본이 이기고, 모순은 보고한다.**

각 불변식: **규칙 → 왜 존재 → 근거(파일:라인) → 위반 예시.**

---

## INV-1. min_peers = 5 고정 (낮추기 금지)

- **규칙:** benchmark 판정을 내는 최소 계산가능 peer 수는 5. 값을 낮춰 억지로 판정을 만들지 않는다.
- **왜:** peer가 적으면 median/IQR 분포가 성립하지 않아 이상탐지가 통계적 의미를 잃는다. 낮추면 노이즈를 "판정"으로 둔갑시킨다.
- **근거:** `config/settings.yaml:13` (`min_peers: 5`), `references/methodology.md:41,51`.
- **위반 예시:** UI/실행에서 `min_peers`를 3으로 내려 INSUFFICIENT_PEERS를 줄이기.

## INV-2. 산업 prefix 3자리 유지 (2자리 rollup 금지)

- **규칙:** 산업 그룹핑은 `induty_code` **앞 3자리**. peer가 부족해도 2자리로 넓혀 채우지 않는다.
- **왜:** 2자리로 rollup하면 무관한 업종이 섞여 benchmark가 오염된다. 부족은 채우는 게 아니라 sparse 직접비교(INV-6)로 드러낸다.
- **근거:** `config/settings.yaml:14` (`ksic_prefix_len: 3`), README "2자리 rollup으로 무관한 회사를 섞지 않음", Loop 6 sparse peer 정책.
- **reconcile 완료(Loop 12):** `references/methodology.md:41`에 있던 "1회 KSIC rollup 후" 표현은 Loop 6 sparse-peer 결정 이전 잔재였다. Loop 12에서 해당 줄(및 mirror인 `docs/METHODOLOGY.md:43`)을 **no-rollup + `09_제한적_peer_비교` 표면화**로 수정해 INV-2와 일치시켰다. **모순 해소됨.**

## INV-3. OFS fallback 금지 (CFS 기준)

- **규칙:** 분석 기준 재무제표는 **연결(CFS)**. 별도(OFS)로 조용히 대체하지 않는다.
- **왜:** CFS/OFS를 섞으면 규모·구조가 달라 비율 비교가 왜곡된다. CFS 없으면 fallback이 아니라 **중단·기록**한다.
- **근거:** `config/settings.yaml:9` (`target_fs_div: "CFS"`, "OFS=separate (fallback only)"), `pipeline.py`의 CFS 실패 시 `StopConditionError`(013/비000 halt), `verify`의 "CFS/OFS 미혼합" 체크.
- **위반 예시:** 대상/​peer의 CFS 조회 실패 시 OFS로 자동 대체해 pool에 넣기.

## INV-4. 특정회사 하드코딩 금지 (config에서 조달)

- **규칙:** 회사명·`corp_code`·종목코드·회사별 특수분기를 **코드에 넣지 않는다.** 그런 값은 `config/settings.yaml`·데이터·`mappings/`에서 온다.
- **왜:** 한 표본(삼성전자)에 과적합되면 다음 입력에서 깨진다. 산업/회사 무관하게 **동일 코드 경로**를 써야 감사가능·일반화 가능.
- **근거:** `CLAUDE.md` 절대규칙 §1, `references/safety-rules.md:5-8`.
- **알려진 예외(격리·표기됨, 의도적 보존):** `pipeline.run_loop3/3b`의 60/51/9·780·prefix"264" tripwire·"삼성전자_…" 파일명, `config/settings.yaml`의 CLI 기본값(`target_stock_code: "005930"`), `multi_target_runner.DEFAULT_TARGETS`의 삼성 baseline은 **삼성 2025 MVP 검증 스냅샷**이다(코드 주석 `NOTE(tripwire)`로 격리).
  - **UI 실행 경로(`multi_target_runner.run_target`)는 Loop 11에서 임의 회사로 완전 일반화·검증됐다**(비삼성 CJ제일제당 등 산출물 생성 확인). UI/입력 레이어에는 회사·종목 리터럴이 없다.
  - **CLI/batch 경로의 이 스냅샷은 제거하지 않고 회귀 감지용 검증 자산으로 의도적 보존한다**(Loop 12 결정). 이는 특정회사 결과 분기 하드코딩이 아니라 **알려진 입력(삼성 2025)에 대한 기대값 tripwire**이며, 계산 엔진 불변(INV-7)을 지키는 수단이다. 단, 새 하드코딩은 만들지 않는다.
- **위반 예시:** UI 일반화하면서 `if company == "삼성전자"` 같은 분기 신설.

## INV-5. NOT_COMPUTABLE / INSUFFICIENT_PEERS 은폐 금지

- **규칙:** 계산불가·peer부족·CFS실패·제외 peer를 **조용히 버리지 않는다.** 산출물(08/09 시트)과 라벨·reason으로 표면화한다.
- **왜:** 감사 보조 도구의 신뢰는 "무엇을 못 했는지"를 숨기지 않는 데서 나온다. 조용한 손실은 잘못된 안심을 준다.
- **근거:** `CLAUDE.md` 절대규칙 §3, `references/safety-rules.md:15-18`, `references/methodology.md:42-45`.
- **위반 예시:** NOT_COMPUTABLE 비율을 표에서 빼서 "전부 계산됨"처럼 보이게 하기.

## INV-6. sparse peer 실명 표시 (익명 금지)

- **규칙:** peer가 부족해 통계 판정을 보류할 때 제공하는 직접비교표(09시트)는 **실제 peer 회사명**을 쓴다. "Peer 1/2" 같은 익명화 금지.
- **왜:** 참고 비교의 감사가능성은 "누구와 비교했는가"가 드러날 때만 성립한다. 익명화는 역추적성을 파괴한다.
- **근거:** README §4·§7("실제 peer 회사명 직접 비교"), Loop 6 `sparse_peer_comparison`, `references/safety-rules.md:24`(peer_corp_codes로 풀 구성원 공개).
- **위반 예시:** 09시트에서 회사명을 마스킹하거나 순번으로 바꾸기.

## INV-7. 계산 엔진과 표시 layer 분리 (원본 status/값 불변)

- **규칙:** 표시·해석·문구 보정은 **계산 결과(label·median·IQR·pool·값)를 바꾸지 않는다.** 표시 layer는 원본 status/값을 읽기만 한다.
- **왜:** 표현을 고치려다 계산을 바꾸면 감사 기준선이 흔들린다. Loop 3-B가 "계산 불변"을 명시적으로 검증하는 이유.
- **근거:** `references/safety-rules.md:47-49`, `references/methodology.md:56-61`, `pipeline.run_loop3b`의 `_check_invariance`(Loop3 대비 mismatch=0 강제).
- **위반 예시:** UI/Excel에서 NORMAL을 보기 좋게 하려 fence나 값을 재계산·반올림해 저장.

## INV-8. 판정 표현·색상 중립 (부수 규칙, 함께 지킴)

- **규칙:** HIGH/LOW를 좋음/나쁨·부정·오류의 **결론**으로 쓰지 않는다. 초록/빨강 대신 주황(HIGH)/파랑(LOW)/회색(중립). "위험 없음/문제 없음" 등 금지표현 미사용.
- **왜:** 산출물은 screening 자료다. 결론적 표현은 오독과 과신을 부른다.
- **근거:** `references/safety-rules.md:39-42,47-49`.

---

## 위반 시 절차

1. 개발방: 불변식을 건드리게 되면 **작업 중단 → 보고**(임의 조정 금지).
2. 검증방: 위반 발견 시 **무조건 FAIL** + 위반 불변식 번호·위치 명시.
3. 검토자: 불변식 자체를 바꿔야 한다면 정본(`CLAUDE.md`/`references`)을 먼저 고치고, 이 파일을 뒤따라 갱신한다. **역순 금지.**

## CLAUDE.md 모순 점검 결과 (Loop 10 시점)

- INV-1~8은 `CLAUDE.md` 절대규칙(§1 하드코딩 금지, §2 raw 보호, §3 조용한 손실 금지)과 `references/safety-rules.md`·`methodology.md`와 **모순 없음**(같은 규칙의 구체화).
- **해소됨(Loop 12):** INV-2의 "1회 rollup"(methodology.md:41) vs no-rollup 모순은 `references/methodology.md:41`·`docs/METHODOLOGY.md:43`을 no-rollup 정책으로 수정해 제거했다. 잔여 언급은 `docs/PLAN.md`·`docs/BUILD_PLAN.md`의 **Loop 6 이전 계획 기록**뿐이며(정본 아님), 히스토리로 보존한다.
