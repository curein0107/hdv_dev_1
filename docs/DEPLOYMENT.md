# GitHub 및 Streamlit Community Cloud 배포

문서 버전: 2025.3

## 1. 사전조건

- GitHub 계정과 배포 대상 저장소
- Python 3.12 권장
- 공개 서비스에 사용할 운영기관 정보
- 영구 결과저장이 필요하면 PostgreSQL 접속정보

## 2. 로컬 실행

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

macOS/Linux:

```bash
chmod +x run_local.sh
./run_local.sh
```

## 3. GitHub 업로드

```bash
git init
git add .
git commit -m "Release health data valuation service 2025.3"
git branch -M main
git remote add origin https://github.com/OWNER/REPOSITORY.git
git push -u origin main
```

확인사항:

- `requirements.txt`는 저장소 루트에 유지
- 메인 파일은 `app.py`
- `.streamlit/secrets.toml`은 커밋 금지
- 참조 CSV와 `reference_manifest.json`은 함께 커밋
- GitHub Actions의 `tests` 워크플로 성공 확인

## 3.1 배포 전 사전점검

```bash
python -m compileall app.py src tests scripts
pytest -q
python scripts/preflight.py
```

`preflight.py`는 Step 2~7 파일 해시, 생산 참조표 계산, CSV·Excel·HTML·JSON 생성, 임시 SQLite 저장·조회까지 한 번에 확인한다. 실패하면 배포를 중단한다.

## 4. Streamlit Community Cloud

1. Streamlit Community Cloud에 GitHub 계정을 연결한다.
2. 새 앱 생성 화면에서 GitHub 저장소를 선택한다.
3. 배포 브랜치를 `main`으로 지정한다.
4. Main file path를 `app.py`로 지정한다.
5. Advanced settings에서 Python 3.12와 Secrets를 설정한다.
6. Deploy 후 로그와 health 상태를 확인한다.

공식 배포 문서:

- https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
- https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies
- https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management

## 5. Secrets

### 운영·검증 정보

```toml
[service]
operator_name = "실제 운영기관명"
operator_unit = "책임부서 또는 사업단"
methodology_owner = "평가 프로파일 책임조직"
methodology_basis = "ISO/TS 26040 개발 프레임워크 기반"
assurance_status = "연구·검증용 베타"
assurance_note = "운영기관이 산정 로직과 참조자료 버전을 관리합니다. 외부 표준·참조자료 제공기관이 본 서비스 또는 산출값을 공식 인증·보증하는 것은 아닙니다."
contact_email = "contact@example.org"
copyright_holder = "실제 저작권자"
```

### 선택적 접속 비밀번호

```toml
[auth]
password = "strong-password"
```

### 원격 PostgreSQL

```toml
[database]
url = "postgresql+psycopg://USER:PASSWORD@HOST:5432/DATABASE?sslmode=require"
```

## 6. 저장소 정책

원격 DB가 없으면 `local_data/valuation_results.sqlite3`를 사용한다. Streamlit Community Cloud의 로컬 파일은 재시작·재배포 때 영구보존을 보장하지 않으므로 운영서비스에서는 원격 PostgreSQL을 사용한다.

## 7. 배포 전 운영 게이트

- 실제 운영 법인명·책임부서 승인
- 기관명·로고 사용 승인
- 대표 연락처 등록
- 이용약관·개인정보처리방침 확정
- HIRA·KOICD 등 참조자료의 이용·재배포 조건 확인
- ISO/TS 26040 프레임워크 활용과 공식 인증을 구분하는 문구 확인
- 원격 DB 접근통제·암호화·백업·보존기간 설정
- 데스크톱·태블릿·모바일 사용자 수용성 시험

## 8. 배포 후 수용시험

- 대문 서비스명이 `헬스 데이터 가치 평가 서비스`인지 확인
- 대문에서 `서비스 시작`, `가이드 보기`만 클릭 가능한지 확인
- 서비스 시작 후 정형·비정형 선택화면으로 이동하는지 확인
- 운영 주체·방법론·검증 상태·저작권 표시 확인
- 간편/상세 품질 입력 전환 확인
- 템플릿 다운로드·CSV 업로드·행 추가 확인
- Step 2 의료행위 103건 검색·선택 확인
- `hospital_base_before_addon_krw`가 없고 `fee`가 표시되는지 확인
- Step 3 기관가중치가 한 번만 적용되는지 확인
- Step 6 질병 검색·가중치 확인
- 가치평가 실행, 그래프, 전체 계산추적 확인
- CSV·Excel·HTML·JSON 다운로드 확인
- 최종 결과 저장과 최근 저장목록 확인
- 앱 로그에 비밀값 또는 개인 식별정보가 노출되지 않는지 확인
