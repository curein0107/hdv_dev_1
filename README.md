# 헬스 데이터 가치 평가 서비스

정형 헬스 데이터의 변수 메타정보를 입력받아 **KR-2025 7-Step 모델 기반 순화폐가치**를 계산하는 Python·Streamlit 웹서비스다. 공통 포털에서 정형과 비정형 데이터 평가 영역을 분리해 향후 의료영상, 임상텍스트, 음성, 파형 평가 모듈을 독립적으로 확장할 수 있도록 구성했다.

> 현재 상태: 연구·검증용 베타  
> 기본 운영 주체: 차의과학대학교 연구팀  
> 주의: HIRA, KOICD, ISO가 본 서비스 또는 산출값을 공식 인증·보증하는 것은 아니다.

## 1. 이번 통합 개발 반영사항

### 서비스·UI

- 대문과 브라우저 제목을 **헬스 데이터 가치 평가 서비스**로 통일
- 대문에서는 `서비스 시작`, `가이드 보기` 두 기능만 제공
- 서비스 진입 후 `정형 헬스 데이터`, `비정형 헬스 데이터` 평가영역 선택
- 정형 평가는 실제 계산 엔진 제공, 비정형 평가는 확장 로드맵으로 명시
- 파란색 그라데이션·육각형·뇌/회로 아이콘을 배제한 편집형 공공·연구 서비스 디자인
- 정형선과 비정형 곡선이 가치점에서 만나는 독자 심볼 사용
- 운영 주체, 방법론 책임, 검증 상태, 보증 한계를 상단·홈·사이드바·보고서에 표시
- 전 화면 하단에 저작권과 참조자료 권리 문구 표시
- 가치평가의 정의·산출 목적·해석 한계를 시작 화면에 배치

### 입력·결과

- 데이터셋 기본정보 및 변수 메타정보 입력
- 간편 Step 1 품질입력과 상세 Step 1 품질입력 분리
- CSV 템플릿 다운로드·업로드, 동적 행 추가
- 검사 변수 Step 2 의료행위 선택 및 보수적 자동추천
- 입력 초안 JSON 저장·복원
- 변수별 Step 1~7 전 계산과정 감사추적
- CSV·Excel·HTML 결과보고서·JSON 감사추적 다운로드
- SQLite 또는 PostgreSQL 결과 저장

## 2. 서비스 구조

```text
헬스 데이터 가치 평가 서비스
├─ 서비스 홈
│  ├─ 가치평가 소개
│  ├─ 서비스 시작
│  └─ 가이드 보기
├─ 평가 유형 선택
│  ├─ 정형 헬스 데이터 가치 평가
│  │  ├─ 데이터셋·변수 메타정보 입력
│  │  ├─ Step 2~7 참조 데이터 조회
│  │  ├─ KR-2025 7-Step 가치평가
│  │  └─ 결과·보고서·저장
│  └─ 비정형 헬스 데이터 가치 평가
│     └─ 의료영상·텍스트·음성·파형 확장 로드맵
└─ 운영·검증 정보
```

## 3. 내부 계산 엔진

계산은 `docs/Supplements_Table_1_reference.xlsx`와 `docs/Supplements_Table_2_KR2022_reference.xlsx`의 내부 계산과정을 코드화한 것이다. 중간단계에서 반올림하지 않고 결과 표시·내보내기 단계에서만 형식을 지정한다.

### Step 1. 데이터 품질

```text
Accuracy (%)     = Accurate data count / Non-empty data count × 100
Completeness (%) = Usable data count / Total data count × 100
Consistency (%)  = Rule-compliant data count / Non-empty data count × 100
```

현재 제공 참조자료에는 품질 통과 임계값이 없으므로 Step 1 품질지표는 표시·감사추적에 사용하고 화폐가치의 승수로 사용하지 않는다. 최종 데이터 수량에는 `usable_count`가 반영된다.

### Step 2. 데이터 생성 단가

- Demographics: 5,610원 ÷ 해당 대분류 변수 수
- Questionnaire: 5,610원 ÷ 해당 대분류 변수 수
- Dietary: 5,610원 ÷ 해당 대분류 변수 수
- Examination & Laboratory: `step2_medical_unit_fee.csv`의 `fee`
- Weight & Not Used & Etc: 0원

최신 Step 2 파일은 다음 5개 열로 고정한다.

```text
fee_name_ko, fee_name_en, procedure_group, data_variable, fee
```

`hospital_base_before_addon_krw`는 사용하지 않으며 기본단가 열은 `fee`다. Step 2에는 기관별 가격 열을 두지 않는다.

### Step 3. 데이터 생산기관 규모

```text
Step 3 = Step 2 × (1 + institution_size_weight / 100)
```

| 기관종별 | 가중치 |
|---|---:|
| 의원 | 15% |
| 병원 | 20% |
| 종합병원 | 25% |
| 상급종합병원 | 30% |

기관효과는 Step 3에서 한 번만 반영한다.

### Step 4. 검사 수행 기반비용

```text
Examination allocation = Institution examination fee / Number of examination variables
Step 4 = Step 3 + Examination allocation
```

검사 수행 기반비용은 `Examination & Laboratory` 변수에만 적용한다.

### Step 5. 데이터 관리비

```text
Step 5 = Step 4 × 1.17
```

### Step 6. 질병 희소성

```text
Step 6 = Step 5 × (1 + scarcity_weight / 100)
```

질병코드가 없거나 참조표에 없으면 0%를 적용하고 경고를 기록한다.

### Step 7. 활용 효과성

```text
Step 7 unit value = Step 6 × (1 + effectiveness_weight / 100)
Final variable value = Step 7 unit value × usable_count
```

효과성 가중치는 연구, 임상·공중보건, 정책, 산업·AI 점수 합계와 동일하다.

## 4. Step 2 최신 참조 데이터

파일: `data/step2_medical_unit_fee.csv`

- 대표 의료행위: 103건
- 의료행위군: 19개
- 최소 fee: 850원
- 중앙 fee: 10,740원
- 최대 fee: 488,290원
- 한글명·영문명·행위군·데이터 변수 검색 지원
- 건강보험 전체 수가 전수본이 아니라 헬스 데이터 변수와 직접 연결되는 운영용 선별표

## 5. 프로젝트 구조

```text
health_data_valuation_service_v2025_3/
├─ app.py
├─ requirements.txt
├─ .streamlit/
├─ .github/workflows/tests.yml
├─ assets/
│  ├─ logo.svg
│  ├─ logo.png
│  └─ styles.css
├─ data/
│  ├─ step2_medical_unit_fee.csv
│  ├─ step3_institue_size.csv
│  ├─ step4_examination_fee_kr2025.csv
│  ├─ step5_data_management_cost.csv
│  ├─ step6_disease_scarcity_kr2025.csv
│  ├─ step7_component_reference.csv
│  ├─ service_identity.json
│  └─ reference_manifest.json
├─ docs/
├─ local_data/
├─ src/ts26040_app/
└─ tests/
```

## 6. 로컬 실행

### Windows PowerShell

```powershell
cd health_data_valuation_service_v2025_3
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

또는 `run_local.bat`을 실행한다.

### macOS/Linux

```bash
cd health_data_valuation_service_v2025_3
chmod +x run_local.sh
./run_local.sh
```

## 7. 자동시험

```bash
pytest
python -m compileall app.py src tests scripts
python scripts/preflight.py
```

주요 검증범위:

- Step 2 5개 열·103개 행·19개 행위군
- 단일 `fee` 조회와 Step 3 기관가중치 분리
- Step 1 정확성·완전성·일관성 계산
- Supplement Table 2 회귀값
- Step 2~7 계산체인
- 서비스 운영정보와 보증 문구
- CSV·Excel·HTML·JSON 내보내기
- GitHub Actions 자동시험
- 배포 전 참조 해시·계산·내보내기·SQLite 통합 사전점검(`scripts/preflight.py`)

## 8. GitHub·Streamlit 배포

상세 절차는 `docs/DEPLOYMENT.md`를 따른다.

```bash
git init
git add .
git commit -m "Release health data valuation service 2025.3"
git branch -M main
git remote add origin https://github.com/OWNER/REPOSITORY.git
git push -u origin main
```

Streamlit Community Cloud에서 GitHub 저장소, `main` 브랜치, `app.py`를 선택하고 Secrets를 입력한다. 실제 비밀값은 저장소에 커밋하지 않는다.

## 9. 운영정보 설정

기본값은 `data/service_identity.json`에 있으며, 운영배포에서는 Streamlit Secrets로 덮어쓸 수 있다.

```toml
[service]
operator_name = "실제 운영기관명"
operator_unit = "책임부서 또는 사업단"
methodology_owner = "평가 프로파일 책임조직"
methodology_basis = "ISO/TS 26040 개발 프레임워크 기반"
assurance_status = "연구·검증용 베타"
contact_email = "contact@example.org"
copyright_holder = "실제 저작권자"
```

선택적 접속 비밀번호와 원격 DB:

```toml
[auth]
password = "strong-password"

[database]
url = "postgresql+psycopg://USER:PASSWORD@HOST:5432/DATABASE?sslmode=require"
```

## 10. 운영상 한계

- 현재 산출값은 시장가격이나 법정 감정가가 아니다.
- 품질 통과 임계값은 제공 참조자료에 없어 구현하지 않았다.
- 비정형 데이터 금액 산정 엔진은 아직 구현 대상이다.
- 로컬 SQLite는 Streamlit Community Cloud에서 영구보존을 보장하지 않는다.
- 공개 배포 전 법인명, 담당부서, 연락처, 이용약관, 개인정보처리방침, 외부 참조자료 이용조건을 확정해야 한다.
