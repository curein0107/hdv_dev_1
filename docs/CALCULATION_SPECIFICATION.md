# KR-2025 정형 헬스 데이터 가치평가 계산 사양

문서 버전: 2025.3  
구현 모듈: `src/ts26040_app/valuation.py`

## 1. 적용 참조파일

- `data/step2_medical_unit_fee.csv`
- `data/step3_institue_size.csv`
- `data/step4_examination_fee_kr2025.csv`
- `data/step5_data_management_cost.csv`
- `data/step6_disease_scarcity_kr2025.csv`
- `data/step7_component_reference.csv`
- `docs/Supplements_Table_1_reference.xlsx`
- `docs/Supplements_Table_2_KR2022_reference.xlsx`

## 1.1 산식과 파라미터의 버전 구분

- **계산 순서와 연산 구조**는 Supplement Table 1·2의 7-Step 내부 계산과정을 따른다.
- **현재 적용 파라미터**는 사용자가 제공한 KR-2025 Step 2~7 CSV에서 읽는다.
- Supplement Table 2의 2022년 의원 예시는 회귀시험 기준으로 보존한다. 운영 계산에서는 Step 2 의료행위 `fee`, Step 3 기관종별 가중치, Step 4 기관종별 진찰료, Step 6 KR-2025 희소성 표를 최신 CSV 값으로 대체한다.
- 따라서 본 구현은 “Supplement 산식 + KR-2025 참조 파라미터” 프로파일이며, 2022년 예시값을 현재값으로 오인하지 않는다.

## 2. 입력 단위

평가는 환자 원자료가 아니라 변수 메타정보 단위로 수행한다.

필수 핵심값:

- 변수명
- 구성요소 세부분류
- 전체 데이터 수
- 사용 가능 데이터 수
- 검사 변수의 Step 2 의료행위 또는 직접입력 수가

선택값:

- 변수 설명
- 정확성·일관성 측정용 건수
- ICD-3 질병코드

## 3. Step 1 품질

```text
accuracy_pct     = accurate_count / non_empty_count × 100
completeness_pct = usable_count / total_count × 100
consistency_pct  = rule_compliant_count / non_empty_count × 100
```

- 분모가 0이면 해당 지표는 미산출이다.
- 참조자료에 임계값이 없어 통과/탈락 게이트를 적용하지 않는다.
- 금액 승수로 사용하지 않는다.
- `usable_count`만 최종 수량에 반영한다.

간편모드:

- `non_empty_count = total_count`
- `accurate_count = non_empty_count`
- `rule_compliant_count = non_empty_count`
- `not_used_count = total_count - usable_count`
- `missing_count = 0`

상세모드에서는 입력값을 그대로 사용하고 논리적 범위를 검증한다.

## 4. Step 2 생성 단가

### 4.1 조사·인구학·식이

각 대분류 내 전체 변수 수로 5,610원을 균등 배분한다.

```text
step2 = 5,610 / number_of_variables_in_component_group
```

적용 대분류:

- Demographics data
- Questionnaire data
- Dietary data

### 4.2 검사·검사실

`step2_medical_unit_fee.csv`의 `fee`를 적용한다.

```text
fee_name_ko,fee_name_en,procedure_group,data_variable,fee
```

우선순위:

1. `manual_unit_price_krw > 0`이면 직접입력 수가
2. 선택한 `medical_fee_item`의 정확 일치
3. 의료행위가 비어 있을 때 변수명 또는 설명이 `data_variable` 토큰과 정확 일치
4. 그 외는 오류로 차단

퍼지 유사도는 추천 UI에만 사용하고 계산에 자동 적용하지 않는다.

### 4.3 제외 구성요소

`Weight & Not Used & Etc`는 Step 2를 0으로 둔다.

## 5. Step 3 기관 규모

```text
step3 = step2 × (1 + institution_weight_pct / 100)
```

기관효과는 Step 3에서 한 번만 적용한다. Step 2에는 기관별 단가 열을 두지 않는다.

## 6. Step 4 검사 수행 기반비용

```text
allocation = examination_fee_krw / examination_variable_count
step4 = step3 + allocation
```

- `Examination & Laboratory`에만 allocation을 적용한다.
- 검사 변수가 0개이면 allocation은 0이다.

## 7. Step 5 데이터 관리비

```text
step5 = step4 × (1 + 17 / 100)
```

## 8. Step 6 질병 희소성

```text
step6 = step5 × (1 + scarcity_weight_pct / 100)
```

- ICD-3가 없으면 0%
- 참조표 미존재 코드는 0%와 경고
- 참조표의 음의 가중치(-80, -60, -40, -20, 0)를 그대로 사용

## 9. Step 7 효과성

```text
step7_unit_value = step6 × (1 + effectiveness_weight_pct / 100)
final_variable_value = step7_unit_value × usable_count
```

효과성 가중치는 다음 네 점수 합이다.

- Research
- Clinical/Public Health
- Policy
- Industry/AI

## 10. 반올림

- Decimal 정밀도 28로 계산한다.
- 중간단계에서 반올림하지 않는다.
- UI·CSV·Excel·HTML 표현단계에서만 서식을 적용한다.

## 11. 오류와 경고

오류:

- 변수명 미입력
- 지원하지 않는 구성요소
- 음수 건수
- 사용 가능 데이터 수 > 전체 데이터 수
- 검사 변수의 수가 미매핑
- 상세 품질건수의 범위 위반

경고:

- ICD-3 미존재
- 품질건수 합계 불일치
- 검사 외 변수에 수가 입력
- 자동 정확일치 매핑
- 중복 변수명

## 12. 범위 한계

Supplement Table 2에는 특정 국가조사에 특화된 구강·치과 비용배분 사례가 일부 존재한다. 현재 업로드된 Step 4 CSV와 UI 요구사항은 일반 검사·검사실 배분만 지원하므로 해당 조사특화 예외는 임의 구현하지 않는다.
