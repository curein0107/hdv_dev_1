# 데이터 사전

## 1. 입력 메타정보

| 필드 | 형식 | 의미 |
|---|---|---|
| `variable_name` | 문자 | 변수명 |
| `variable_description` | 문자 | 변수 설명 |
| `component_detail` | 선택형 | Step 7 구성요소 세부분류 |
| `total_count` | 정수 | 전체 데이터 수 |
| `non_empty_count` | 정수 | 비어있지 않은 데이터 수 |
| `accurate_count` | 정수 | 정확한 데이터 수 |
| `rule_compliant_count` | 정수 | 규칙 준수 데이터 수 |
| `usable_count` | 정수 | 최종 가치에 반영할 사용 가능 데이터 수 |
| `not_used_count` | 정수 | 미사용 데이터 수 |
| `missing_count` | 정수 | 결측 데이터 수 |
| `disease_icd3` | 문자 | Step 6 희소성 조회용 ICD-3 |
| `medical_fee_item` | 문자 | Step 2 의료행위 한글명 |
| `manual_unit_price_krw` | 실수 | Step 2 직접입력 수가; 0보다 크면 카탈로그보다 우선 |

## 2. Step 2 의료행위 수가

파일: `step2_medical_unit_fee.csv`

| 필드 | 의미 |
|---|---|
| `fee_name_ko` | 의료행위 한글명; UI 선택키 |
| `fee_name_en` | 의료행위 영문명 |
| `procedure_group` | 의료행위군 |
| `data_variable` | 해당 행위로 생성되는 대표 데이터 변수·검색 토큰 |
| `fee` | Step 2 공통 기본단가(KRW) |

`hospital_base_before_addon_krw`와 기관별 가격 열은 사용하지 않는다.

## 3. Step 3 기관규모

| 필드 | 의미 |
|---|---|
| `institute_size` | 기관코드 |
| `institute_size_weigth` | 기관규모 가중치(원본 파일명 유지) |

애플리케이션에서는 `teritary-hospital_large` 오탈자를 `tertiary-hospital_large`로 정규화한다.

## 4. Step 4 검사 수행비

| 필드 | 의미 |
|---|---|
| `institute_size_examination` | 기관코드 |
| `examination_fee` | 기관종별 초진진찰료(KRW) |

## 5. Step 5 관리비

| 필드 | 의미 |
|---|---|
| `data_management_cost` | 관리요인명 |
| `data_management_weigth` | 관리비 가중치 |

## 6. Step 6 질병 희소성

| 필드 | 의미 |
|---|---|
| `ranking` | 환자 수 순위 |
| `icd3` | ICD-3 코드 |
| `disease_name` | 질병명 |
| `patient_count` | 환자 수 |
| `morbidity_pct` | 유병률(%) |
| `morbidity_group` | 유병률 구간 |
| `scarcity_weight_pct` | 희소성 가중치(%) |

## 7. Step 7 효과성

| 필드 | 의미 |
|---|---|
| `component_code` | 구성요소 코드 |
| `component_detail` | 구성요소 세부분류 |
| `research_score` | 연구 활용 점수 |
| `clinical_public_health_score` | 임상·공중보건 점수 |
| `policy_score` | 정책 점수 |
| `industry_ai_score` | 산업·AI 점수 |
| `effectiveness_weight` | 네 점수 합산 가중치 |

## 8. 주요 결과 필드

| 필드 | 의미 |
|---|---|
| `step1_accuracy_pct` | Step 1 정확성 |
| `step1_completeness_pct` | Step 1 완전성 |
| `step1_consistency_pct` | Step 1 일관성 |
| `step2_fee_krw` | Step 2 단위가치 |
| `step3_value_krw` | 기관규모 반영 단위가치 |
| `step4_value_krw` | 검사 수행 기반비용 반영 단위가치 |
| `step5_value_krw` | 관리비 반영 단위가치 |
| `step6_value_krw` | 희소성 반영 단위가치 |
| `step7_unit_value_krw` | 효과성 반영 최종 단위가치 |
| `final_variable_value_krw` | 변수별 총가치 |
| `warning` | 변수별 평가 경고 |
