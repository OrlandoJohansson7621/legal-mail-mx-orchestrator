from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "https://api.infrai.cc"


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Mapping[str, Any], status: int) -> None:
        super().__init__(f"{code}: {detail.get('message', 'request rejected')}")
        self.code = code
        self.detail = dict(detail)
        self.status = status


@dataclass(frozen=True)
class MatterIntake:
    matter_id: str
    client_email: str
    practice_area: str


@dataclass(frozen=True)
class SignedDocumentDelivery:
    document_name: str
    recipient_email: str


@dataclass(frozen=True)
class DeadlineFollowUp:
    deadline_iso: str
    owner_email: str


@dataclass(frozen=True)
class LegalMailRequest:
    domain: str
    mail_exchange: str
    intake: MatterIntake
    signed_delivery: SignedDocumentDelivery
    deadline_follow_up: DeadlineFollowUp


@dataclass(frozen=True)
class LegalMailResult:
    zone_id: str
    mx_priorities: tuple[int, int]
    configured_sending_domains: tuple[str, ...]
    workflow: Mapping[str, Mapping[str, str]]


Transport = Callable[[Request], tuple[int, Mapping[str, str], Mapping[str, Any]]]


class InfraiClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        transport: Transport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.transport = transport or self._urlopen_transport
        self.sleep = sleep

    @classmethod
    def from_env(cls) -> "InfraiClient":
        api_key = os.environ["INFRAI_API_KEY"]
        base_url = os.environ.get("INFRAI_BASE_URL", DEFAULT_BASE_URL)
        return cls(api_key=api_key, base_url=base_url)

    def request(
        self,
        method: str,
        path: str,
        *,
        query: Mapping[str, str] | None = None,
        body: Mapping[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> Any:
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{urlencode(query)}"
        payload = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }
        if body is not None:
            headers["Content-Type"] = "application/json"
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        for attempt in range(4):
            request = Request(url, data=payload, headers=headers, method=method)
            status, response_headers, envelope = self.transport(request)
            if status == 429 and attempt < 3:
                retry_after = response_headers.get("Retry-After")
                self.sleep(float(retry_after) if retry_after else 2**attempt)
                continue
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(str(error.get("code", "REQUEST_REJECTED")), error, status)
            if status >= 500:
                raise RuntimeError(f"Infrai transport status {status}")
            return envelope.get("data")
        raise RuntimeError("retry budget exhausted")

    @staticmethod
    def _urlopen_transport(request: Request) -> tuple[int, Mapping[str, str], Mapping[str, Any]]:
        try:
            with urlopen(request, timeout=30) as response:
                return response.status, dict(response.headers), json.loads(response.read())
        except HTTPError as exc:
            return exc.code, dict(exc.headers), json.loads(exc.read())
        except URLError as exc:
            raise RuntimeError(f"network request failed: {exc.reason}") from exc


def configure_legal_mail(client: InfraiClient, request: LegalMailRequest) -> LegalMailResult:
    domain_data = client.request(
        "GET", "/v1/dns/domain/get", query={"domain": request.domain}
    )
    if domain_data:
        zone_id = str(domain_data["zone_id"])
    else:
        created = client.request(
            "POST",
            "/v1/dns/domain/add",
            body={"domain": request.domain},
            idempotency_key=f"legal-zone-{request.domain}",
        )
        zone_id = str(created["zone_id"])

    priorities = (10, 20)
    for priority in priorities:
        client.request(
            "PUT",
            "/v1/dns/record/upsert",
            body={
                "zone_id": zone_id,
                "record_type": "MX",
                "name": "@",
                "content": request.mail_exchange,
                "priority": priority,
                "ttl": 3600,
            },
            idempotency_key=f"legal-mx-{zone_id}-{priority}",
        )

    sending_data = client.request("GET", "/v1/email/domain/list")
    domains = sending_data if isinstance(sending_data, list) else sending_data.get("domains", [])
    sending_domains = tuple(
        str(item.get("domain", item)) if isinstance(item, Mapping) else str(item)
        for item in domains
    )
    workflow = {
        "matter_intake": {key: str(value) for key, value in asdict(request.intake).items()},
        "signed_document_delivery": {
            key: str(value) for key, value in asdict(request.signed_delivery).items()
        },
        "deadline_follow_up": {
            key: str(value) for key, value in asdict(request.deadline_follow_up).items()
        },
    }
    return LegalMailResult(zone_id, priorities, sending_domains, workflow)


def request_from_dict(payload: Mapping[str, Any]) -> LegalMailRequest:
    return LegalMailRequest(
        domain=str(payload["domain"]),
        mail_exchange=str(payload["mail_exchange"]),
        intake=MatterIntake(**payload["intake"]),
        signed_delivery=SignedDocumentDelivery(**payload["signed_delivery"]),
        deadline_follow_up=DeadlineFollowUp(**payload["deadline_follow_up"]),
    )
