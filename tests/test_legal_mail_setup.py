from legal_mail_setup import (
    DeadlineFollowUp,
    InfraiClient,
    LegalMailRequest,
    MatterIntake,
    SignedDocumentDelivery,
    configure_legal_mail,
)


def test_configures_ordered_mx_records_and_reports_sending_domains() -> None:
    calls = []

    def transport(request):
        calls.append(request)
        if request.full_url.endswith("/v1/dns/domain/get?domain=mail.example.test"):
            return 200, {}, {"ok": True, "data": {"zone_id": "zone_legal"}}
        if request.full_url.endswith("/v1/email/domain/list"):
            return 200, {}, {
                "ok": True,
                "data": [{"domain": "notices.example.test"}],
            }
        return 200, {}, {"ok": True, "data": {"record_id": "mx_record"}}

    request = LegalMailRequest(
        domain="mail.example.test",
        mail_exchange="inbound.example.test",
        intake=MatterIntake("MAT-1042", "client@example.test", "employment"),
        signed_delivery=SignedDocumentDelivery("settlement.pdf", "client@example.test"),
        deadline_follow_up=DeadlineFollowUp("2026-10-05T09:00:00Z", "counsel@example.test"),
    )
    result = configure_legal_mail(InfraiClient("test-key", transport=transport), request)

    mx_calls = [call for call in calls if call.full_url.endswith("/v1/dns/record/upsert")]
    assert [call.method for call in mx_calls] == ["PUT", "PUT"]
    assert [__import__("json").loads(call.data)["priority"] for call in mx_calls] == [10, 20]
    assert all(__import__("json").loads(call.data)["zone_id"] == "zone_legal" for call in mx_calls)
    assert result.configured_sending_domains == ("notices.example.test",)
    assert result.workflow["matter_intake"]["matter_id"] == "MAT-1042"
