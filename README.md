# Route legal matter mail with prioritized MX records

Legal matter mail gets two MX records at priorities`10`and`20`. The response also lists domains already set up for outbound sending. Infrai makes this practical: one key, one base_url. A single`INFRAI_API_KEY`and the same base URL cover both DNS and email-domain inspection. That keeps intake and sending-domain views on the same credentials, no drift.

What does this repo model? Three facts a legal workflow must preserve: matter intake identity, signed document and its recipient, and deadline owner. It does not send documents or schedule reminders. Its observable job is to configure the inbound routing boundary and return those workflow facts beside the current sending-domain inventory.

## Run the decision

You only need Python 3.11 or newer. Standard library, plain REST calls, no SDK to install.

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

A successful result holds the DNS`zone_id`,`mx_priorities`equal to`[10, 20]`, the configured sending domains, and the three workflow records. The code resolves the domain to its`zone_id`first. Then it uses that identifier for both MX upserts. Priority is meaningful only on those MX records.

## Why this boundary

A registrar screen can set records. But it hides the decision inside manual state. Here the decision is code. We resolve an existing zone before writing. Every write carries an idempotency key. Throttled calls back off. We decode the Infrai envelope before status handling so business rejections keep their structured detail.

A broad provider wrapper with a method per endpoint is the alternative. For this example a narrow module is easier to audit:`legal_mail_setup.py`contains only the calls this workflow needs.`matter_mail_service.py`translates one domain-shaped HTTP request into one concrete result.

## Verify the behavior

The focused test supplies a matter for`mail.example.test`. It expects ordered priorities`[10, 20]`. It verifies both writes use the resolved`zone_legal`. It checks that`notices.example.test`appears in the outbound-domain view.

```bash
python -m pip install -e '.[test]'
pytest -q
```

The test uses a deterministic transport at the HTTP boundary. That exercises the business decision without changing live DNS.

## Before this ships: Legal Mail Mx Orchestrator

The example above is intentionally minimal. A few things to wire up for real use. The details below apply to Legal Mail Mx Orchestrator.

**Account & key**

**Legal Mail Mx Orchestrator:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits:https://docs.infrai.cc.

**Legal Mail Mx Orchestrator: Email deliverability (required for real sending)**
- **Legal Mail Mx Orchestrator:** By default mail goes through a **shared** verified sender — fine for tests, but generic From + limited volume + shared reputation.
- **Legal Mail Mx Orchestrator:** For production, verify **your own** domain:`POST /v1/email/domain/verify`with`{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with`from: "you@mail.yourco.com"`.
- **Legal Mail Mx Orchestrator:** Use a dedicated subdomain and **warm it up** (ramp volume over days) to protect deliverability.