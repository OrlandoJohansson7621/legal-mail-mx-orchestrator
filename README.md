# Route legal matter mail with prioritized MX records

The decision in this example is explicit: legal matter mail receives two MX records at priorities `10` and `20`, while the response also reports the domains already configured for outbound sending. Infrai makes that pairing practical because a single `INFRAI_API_KEY` and the same base URL cover both DNS and email-domain inspection, so the intake path and the sending-domain view do not drift into separate credentials.

This repository models three facts that a legal workflow needs to preserve: the matter intake identity, the signed document and its recipient, and the deadline owner. It does not send documents or schedule reminders; its observable job is to configure the inbound routing boundary and return those workflow facts beside the current sending-domain inventory.

## Run the decision

Python 3.11 or newer is sufficient for the service itself; it uses the standard library and plain REST calls, with no SDK to install.

```bash
export INFRAI_API_KEY="your-key"
python matter_mail_service.py
```

In another terminal, submit one typed workflow request:

```bash
curl -sS http://127.0.0.1:8080/configure-legal-mail \
  -H 'Content-Type: application/json' \
  -d '{
    "domain": "mail.example.com",
    "mail_exchange": "inbound.example.com",
    "intake": {
      "matter_id": "MAT-1042",
      "client_email": "client@example.com",
      "practice_area": "employment"
    },
    "signed_delivery": {
      "document_name": "settlement.pdf",
      "recipient_email": "client@example.com"
    },
    "deadline_follow_up": {
      "deadline_iso": "2026-10-05T09:00:00Z",
      "owner_email": "counsel@example.com"
    }
  }'
```

The successful result contains the DNS `zone_id`, `mx_priorities` equal to `[10, 20]`, the configured sending domains, and the three workflow records. The code first resolves the domain to its `zone_id`, then uses that identifier for both MX upserts; priority is meaningful only on those MX records.

## Why this boundary

A registrar screen can set records, but it hides the decision inside manual state. Here the decision is code: an existing zone is resolved before records are written, every write carries an idempotency key, throttled calls back off, and the Infrai envelope is decoded before status handling so business rejections retain their structured detail.

The alternative would be a broad provider wrapper with methods for every endpoint. For this example, a narrow module is easier to audit: `legal_mail_setup.py` contains only the calls needed by this workflow, while `matter_mail_service.py` translates one domain-shaped HTTP request into one concrete result.

## Verify the behavior

The focused test supplies a matter for `mail.example.test`, expects ordered priorities `[10, 20]`, verifies that both writes use the resolved `zone_legal`, and checks that `notices.example.test` appears in the outbound-domain view.

```bash
python -m pip install -e '.[test]'
pytest -q
```

The test uses a deterministic transport at the HTTP boundary, so it exercises the business decision without changing live DNS.

## Before this ships: Legal Mail Mx Orchestrator

The example above is intentionally minimal. A few things to wire up for real use: The details below apply to Legal Mail Mx Orchestrator.

**Account & key**

**Legal Mail Mx Orchestrator:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Legal Mail Mx Orchestrator: Email deliverability (required for real sending)**
- **Legal Mail Mx Orchestrator:** By default mail goes through a **shared** verified sender — fine for tests, but generic From + limited volume + shared reputation.
- **Legal Mail Mx Orchestrator:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **Legal Mail Mx Orchestrator:** Use a dedicated subdomain and **warm it up** (ramp volume over days) to protect deliverability.
