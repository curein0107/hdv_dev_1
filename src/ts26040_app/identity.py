from __future__ import annotations

import json
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, Mapping

from .config import SERVICE_IDENTITY_PATH


@dataclass(frozen=True)
class ServiceIdentity:
    operator_name: str
    operator_unit: str
    methodology_owner: str
    methodology_basis: str
    assurance_status: str
    assurance_note: str
    reference_sources: tuple[str, ...]
    data_handling_note: str
    contact_email: str
    copyright_holder: str


_DEFAULTS: dict[str, Any] = {
    "operator_name": "운영기관 정보 등록 필요",
    "operator_unit": "",
    "methodology_owner": "평가 프로파일 운영팀",
    "methodology_basis": "ISO/TS 26040 개발 프레임워크 기반",
    "assurance_status": "연구·검증용 베타",
    "assurance_note": (
        "운영기관이 산정 로직과 참조자료 버전을 관리합니다. 외부 표준·참조자료 "
        "제공기관이 본 서비스 또는 산출값을 공식 인증·보증하는 것은 아닙니다."
    ),
    "reference_sources": (),
    "data_handling_note": "환자 원자료가 아닌 데이터셋·변수 단위 메타정보 입력을 원칙으로 합니다.",
    "contact_email": "",
    "copyright_holder": "헬스 데이터 가치평가 서비스 운영팀",
}


def _read_identity_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        loaded = json.load(handle)
    if not isinstance(loaded, dict):
        raise ValueError("service_identity.json의 최상위 값은 객체여야 합니다.")
    return loaded


def load_service_identity(
    overrides: Mapping[str, Any] | None = None,
    path: Path = SERVICE_IDENTITY_PATH,
) -> ServiceIdentity:
    """Load public operator/assurance information.

    The repository JSON provides deployable defaults. A Streamlit ``[service]``
    secrets block can override any field without changing source control.
    Empty override values are ignored so that an incomplete secrets block does
    not erase a valid repository value.
    """

    payload = dict(_DEFAULTS)
    payload.update(_read_identity_file(path))
    if overrides:
        valid_names = {item.name for item in fields(ServiceIdentity)}
        for key, value in overrides.items():
            if key in valid_names and value not in (None, "", []):
                payload[key] = value

    sources = payload.get("reference_sources", ())
    if isinstance(sources, str):
        sources = tuple(item.strip() for item in sources.split(";") if item.strip())
    else:
        sources = tuple(str(item).strip() for item in sources if str(item).strip())

    return ServiceIdentity(
        operator_name=str(payload.get("operator_name", "")).strip(),
        operator_unit=str(payload.get("operator_unit", "")).strip(),
        methodology_owner=str(payload.get("methodology_owner", "")).strip(),
        methodology_basis=str(payload.get("methodology_basis", "")).strip(),
        assurance_status=str(payload.get("assurance_status", "")).strip(),
        assurance_note=str(payload.get("assurance_note", "")).strip(),
        reference_sources=sources,
        data_handling_note=str(payload.get("data_handling_note", "")).strip(),
        contact_email=str(payload.get("contact_email", "")).strip(),
        copyright_holder=str(payload.get("copyright_holder", "")).strip(),
    )
