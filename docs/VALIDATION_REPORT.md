# 검증 보고서

빌드: `health_data_valuation_service_v2025_3`  
서비스 버전: `2025.3 · BETA`  
검증일: 2026-08-11

## 1. 총괄 결과

| 검증 항목 | 결과 |
|---|---:|
| Python 문법 컴파일 | **PASS** |
| 배포 전 통합 preflight | **PASS** |
| pytest 자동시험 | **21 passed** |
| Step 2 최신 업로드 파일 일치 | **PASS** |
| Step 2 스키마 | **5개 열 PASS** |
| Supplement Table 회귀값 | **PASS** |
| Step 2~7 통합 계산 | **PASS** |
| CSV·Excel·HTML·JSON 내보내기 | **PASS** |
| SQLite 저장·최근 목록 조회 | **PASS** |
| 서비스 운영정보·보증범위 출력 | **PASS** |
| 정적 UI 목업 렌더링 | **PASS** |
| Streamlit 브라우저 런타임 | **미실행** |

검증 환경의 Python은 3.13.5였다. 배포 구성은 Streamlit Community Cloud와 GitHub Actions에서 Python 3.12를 사용하도록 지정했다.

## 2. 검수의견 반영 확인

| 검수사항 | 구현 결과 |
|---|---|
| 대문 명칭 통일 | 모든 화면·보고서·브라우저 제목을 `헬스 데이터 가치 평가 서비스`로 통일 |
| 정형·비정형 분리 | `서비스 시작 → 평가 유형 선택 → 정형/비정형` 구조 구현 |
| 확장 가능한 서비스 구조 | 공통 포털과 데이터 형식별 독립 평가 프로파일로 분리 |
| AI 생성형 디자인 축소 | 파란 그라데이션·육각형·뇌/회로 상징을 제거하고 저채도 편집형 디자인 적용 |
| 창의적 로고 | 정형 데이터선과 비정형 곡선이 하나의 가치점에서 만나는 심볼 적용 |
| 운영·보증 정보 | 상단·홈·사이드바·운영페이지·결과 산출물에 운영 주체와 보증 한계 표시 |
| 카피라이트 | 전 화면 하단에 저작권·참조자료 권리·문의영역 표시 |
| 가치평가 소개 | 첫 화면에 정의, 계산경로, 산출값의 해석 한계 배치 |
| context UI 기능 | 템플릿, CSV 업로드, 행 추가, 좌측 메뉴, 결과보고서, 입력복귀, 결과저장 구현 |

홈에서는 context 요구에 따라 `서비스 시작`과 `가이드 보기`만 주요 행동버튼으로 제공한다. 정형 입력화면에서는 데이터셋 기본정보와 변수 메타정보를 입력하고, 결과화면에서는 요약지표·차트·변수별 결과·전체 계산추적·내보내기·저장을 제공한다.

## 3. Step 2 최신 데이터 검증

적용 파일: `data/step2_medical_unit_fee.csv`

### 3.1 원본 일치

프로젝트 파일은 사용자가 업로드한 최신 `step2_medical_unit_fee(1).csv`와 바이트 단위로 일치한다.

```text
SHA-256: 177158ea548b54c2cbe4df6e470d792a1b987a3b6fcb569174a58e6f3a42f356
```

Step 3~7 프로젝트 파일도 같은 시점에 업로드된 최신 파일과 바이트 단위로 일치한다.

### 3.2 스키마

```text
fee_name_ko,fee_name_en,procedure_group,data_variable,fee
```

- `hospital_base_before_addon_krw`: 없음
- 기관별 Step 2 가격 컬럼: 없음
- 공통 단가 컬럼: `fee`
- 기관효과: Step 3에서 한 번만 적용

### 3.3 데이터 프로파일

| 항목 | 값 |
|---|---:|
| 대표 의료행위 | 103건 |
| 의료행위군 | 19개 |
| 중복 한글 의료행위명 | 0건 |
| 0 이하 fee | 0건 |
| 최소 fee | 850원 |
| 중앙 fee | 10,740원 |
| 최대 fee | 488,290원 |

생산 참조표 기준 `헤모글로빈 A1c`는 7,350원, `트리글리세라이드`는 3,790원으로 조회된다. Step 2는 기관중립 단일 fee이고, 의원·병원·종합병원·상급종합병원 효과는 Step 3 가중치로 분리된다.

## 4. Supplement Table 계산과정 검증

### Step 1 — 데이터 품질

```text
Accuracy (%)     = Accurate count / Non-empty count × 100
Completeness (%) = Usable count / Total count × 100
Consistency (%)  = Rule-compliant count / Non-empty count × 100
```

제공된 Supplement Table에는 품질 통과 임계값이나 화폐가치 승수가 제시되지 않았다. 따라서 품질지표는 표시·감사추적에 사용하고, 최종 수량에는 `usable_count`만 반영한다.

### Step 2 — 생성 단가

```text
Demographics / Questionnaire / Dietary
= 5,610원 ÷ 해당 Component Survey Group의 변수 수

Examination & Laboratory
= step2_medical_unit_fee.csv의 fee

Weight & Not Used & Etc
= 0원
```

### Step 3~7

```text
Step 3 = Step 2 × (1 + 기관규모 가중치)
Step 4 = Step 3 + 기관종별 초진진찰료 / 검사변수 수
Step 5 = Step 4 × 1.17
Step 6 = Step 5 × (1 + 질병 희소성 가중치)
Step 7 단위가치 = Step 6 × (1 + 효과성 가중치)
최종 변수 가치 = Step 7 단위가치 × 사용 가능 데이터 수
```

모든 중간 계산은 Decimal 정밀도 28로 수행하고 계산 중 반올림하지 않는다.

### Supplement Table 2 회귀값

`region` 예시를 30개 Demographics 변수와 의원 15% 조건으로 재현했다.

| 계산값 | 기대값 | 결과 |
|---|---:|---:|
| Step 2 | 187.000000 | PASS |
| Step 3 | 215.050000 | PASS |
| Step 5 | 251.608500 | PASS |
| Step 7 단위가치 | 289.349775 | PASS |
| 최종 가치 | 1,812,776.340375 | PASS |

## 5. 생산 참조표 통합 스모크 테스트

기본 예시:

- 데이터셋: 당뇨병 정형 임상 데이터셋
- 기관종별: 종합병원
- 변수: Sex, Age, Smoking, TG, HbA1c
- 전체 변수 수: 5
- 사용 가능 데이터 수: 4,550
- 평균 완전성: 91.0%
- 총가치: **25,455,441.375원**
- 경고: 없음

참조표 행 수:

| Step | 행 수 |
|---|---:|
| Step 2 | 103 |
| Step 3 | 4 |
| Step 4 | 4 |
| Step 5 | 1 |
| Step 6 | 1,667 |
| Step 7 | 12 |

내보내기 스모크 결과:

| 형식 | 결과 | 생성 크기 |
|---|---:|---:|
| CSV | PASS | 3,268 bytes |
| Excel | PASS | 약 12 KB¹ |
| HTML 결과보고서 | PASS | 7,229 bytes |
| JSON 감사추적 | PASS | 11,117 bytes |

¹ Excel 파일은 ZIP 메타데이터의 생성시각 때문에 실행마다 수 바이트 차이가 날 수 있으며, preflight는 비어 있지 않은 유효 파일 생성을 검증한다.

SQLite 저장 후 최근 결과 목록에서 동일 run ID를 조회해 저장·조회 체인을 확인했다.

### 통합 preflight 결과

`scripts/preflight.py`로 다음을 한 번에 재검증했다.

- Step 2~7 파일 SHA-256 고정값
- 생산 참조표 행 수와 필수 열
- 기본 예시 5개 변수의 Step 2~7 총가치
- CSV·Excel·HTML·JSON 결과 생성
- 임시 SQLite 저장·최근 목록 조회

실행 결과는 **PASS**였으며 총가치 `25,455,441.375원`, 사용 가능 데이터 `4,550건`, 평균 완전성 `91.0%`를 재현했다.

## 6. UI·디자인 정적 검증

다음 네 화면의 정적 목업을 앱의 동일 로고·CSS·화면구조를 이용해 렌더링했다.

- `UI_HOME_PREVIEW.png`
- `UI_PROFILE_SELECTION_PREVIEW.png`
- `UI_INPUT_PREVIEW.png`
- `UI_RESULT_PREVIEW.png`

검증사항:

- 서비스명이 모든 화면에서 동일함
- 정형·비정형 선택구조가 분명함
- 운영 주체와 베타 상태가 상단에 표시됨
- 가치평가 소개와 계산논리가 첫 화면에 나타남
- 좌측 메뉴, 입력 표, 결과 KPI, 차트, 보고서 버튼, 저작권 하단이 포함됨
- 앱 CSS와 로고에 선형·원뿔형 그라데이션이 없음

정적 목업은 실제 Streamlit 런타임 캡처가 아니라 동일 디자인 소스에 기반한 검수 이미지다.

## 7. GitHub·배포 구성 검증

- 루트 `app.py`: 존재
- 루트 `requirements.txt`: 존재
- `.streamlit/config.toml`: 존재
- `.streamlit/secrets.toml.example`: 존재
- 실제 `.streamlit/secrets.toml`: Git 제외
- `.github/workflows/tests.yml`: push·pull request 자동시험
- workflow 단계: 문법 컴파일 → pytest 21개 → 통합 preflight
- GitHub Actions: `actions/checkout@v7`, `actions/setup-python@v7`
- workflow 권한: `contents: read`
- 배포 Python: 3.12
- 참조 CSV와 해시 manifest: 저장소 포함

## 8. 미실행 범위와 배포 전 게이트

빌드 컨테이너에는 Streamlit 패키지가 없고 외부 패키지 설치 네트워크가 차단되어 실제 Streamlit 브라우저 런타임은 실행하지 못했다. 문법, 도메인 계산, 참조표, 내보내기, 저장, 정적 UI 구조는 검증했다.

배포 후 반드시 확인할 항목:

1. 실제 Streamlit 데스크톱·태블릿·모바일 렌더링
2. `st.data_editor`, 파일업로드, 다운로드, 탭, 사이드바 동작
3. Streamlit Secrets의 운영기관·비밀번호·DB 설정
4. PostgreSQL 접근통제·암호화·백업
5. 실제 법인명·책임부서·기관명·로고 사용 승인
6. 이용약관·개인정보처리방침·참조자료 재배포 조건
7. 접근성, 키보드 탐색, 명도 대비 사용자 수용성 시험

## 9. 보증 한계

현재 표시되는 운영기관명은 개발용 기본값이다. 공개 배포 전 실제 책임조직 승인이 필요하다. HIRA와 KOICD는 참조자료 출처이며 본 서비스 또는 산출값의 보증기관이 아니다. ISO/TS 26040 개발 프레임워크 활용은 ISO 인증 또는 공식 적합성 보증을 의미하지 않는다. 산출값은 모델 기반 순화폐가치로서 시장가격, 보험 청구액, 회계상 공정가치 또는 법정 감정가와 동일하지 않다.
