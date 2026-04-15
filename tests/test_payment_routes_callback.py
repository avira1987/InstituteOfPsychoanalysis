"""HTTP callback for payment gateway: SEP form fields (state, ResNum) and pending lookup."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.main import app
from app.api import payment_routes
from app.models.operational_models import PaymentPending, ProcessInstance
from app.services.payment_gateway import PaymentResponse


@pytest.mark.asyncio
async def test_callback_post_sep_lowercase_state_and_get_query_params(db_session, sample_student, monkeypatch):
    """Saman sends state (lowercase) and ResNum; GET redirect uses query string; pending keyed by authority=ResNum."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # ── POST form (typical SEP) ─────────────────────────────
        inst_id = uuid.uuid4()
        inst = ProcessInstance(
            id=inst_id,
            process_code="fee_determination",
            student_id=sample_student.id,
            current_state_code="triggered",
            is_completed=False,
            is_cancelled=False,
            context_data={},
        )
        db_session.add(inst)
        await db_session.flush()
        res_num = "a1b2c3d4e5f67890"
        pending = PaymentPending(
            id=uuid.uuid4(),
            authority=res_num,
            gateway_track_id="SEP-TOKEN-TEST",
            instance_id=inst_id,
            student_id=sample_student.id,
            amount=5_000_000,
        )
        db_session.add(pending)
        await db_session.commit()

        calls = []

        async def fake_verify_counting(ref, amt):
            calls.append((ref, amt))
            return PaymentResponse(success=True, authority=ref, ref_id="RRN-1")

        monkeypatch.setattr(payment_routes, "verify_payment", fake_verify_counting)

        r = await client.post(
            "/api/payment/callback",
            params={"format": "json"},
            data={
                "state": "OK",
                "RefNum": "REF-SEP-1",
                "ResNum": res_num,
                "Amount": "5000000",
            },
        )
        assert r.status_code == 200
        assert r.json().get("success") is True
        assert calls == [("REF-SEP-1", 5_000_000)]

        r2 = await db_session.execute(select(PaymentPending).where(PaymentPending.authority == res_num))
        assert r2.scalars().first() is None

        # ── GET query (browser redirect) ─────────────────────────
        inst_id2 = uuid.uuid4()
        inst2 = ProcessInstance(
            id=inst_id2,
            process_code="fee_determination",
            student_id=sample_student.id,
            current_state_code="triggered",
            is_completed=False,
            is_cancelled=False,
            context_data={},
        )
        db_session.add(inst2)
        await db_session.flush()
        res_num2 = "getcallback123456"
        pending2 = PaymentPending(
            id=uuid.uuid4(),
            authority=res_num2,
            gateway_track_id="tok2",
            instance_id=inst_id2,
            student_id=sample_student.id,
            amount=1_000_000,
        )
        db_session.add(pending2)
        await db_session.commit()

        calls.clear()

        async def fake_verify_2(ref, amt):
            calls.append((ref, amt))
            return PaymentResponse(success=True, authority=ref, ref_id="RRN-2")

        monkeypatch.setattr(payment_routes, "verify_payment", fake_verify_2)

        r3 = await client.get(
            "/api/payment/callback",
            params={
                "state": "OK",
                "RefNum": "REF-GET-1",
                "ResNum": res_num2,
                "Amount": "1000000",
                "format": "json",
            },
        )
        assert r3.status_code == 200
        assert r3.json().get("success") is True
        assert calls == [("REF-GET-1", 1_000_000)]

        # ── POST بدون format=json: ریدایرکت مرورگر به پنل ─────────
        inst_id3 = uuid.uuid4()
        inst3 = ProcessInstance(
            id=inst_id3,
            process_code="fee_determination",
            student_id=sample_student.id,
            current_state_code="triggered",
            is_completed=False,
            is_cancelled=False,
            context_data={},
        )
        db_session.add(inst3)
        await db_session.flush()
        res_num3 = "browseredir1234567"
        pending3 = PaymentPending(
            id=uuid.uuid4(),
            authority=res_num3,
            gateway_track_id="tokBR",
            instance_id=inst_id3,
            student_id=sample_student.id,
            amount=100_000,
        )
        db_session.add(pending3)
        await db_session.commit()

        async def fake_verify_br(ref, amt):
            return PaymentResponse(success=True, authority=ref, ref_id="RRN-BR")

        monkeypatch.setattr(payment_routes, "verify_payment", fake_verify_br)

        r4 = await client.post(
            "/api/payment/callback",
            follow_redirects=False,
            data={
                "state": "OK",
                "RefNum": "REF-BR",
                "ResNum": res_num3,
                "Amount": "100000",
            },
        )
        assert r4.status_code == 303
        loc = r4.headers.get("location") or ""
        assert "payment=success" in loc
        assert "panel/portal/student" in loc
