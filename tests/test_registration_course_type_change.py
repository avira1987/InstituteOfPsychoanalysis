"""تست تغییر نوع دورهٔ ثبت‌نام اولیه."""

import uuid

import pytest

from app.services.student_service import StudentService, EXPECTED_REGISTRATION_CODE


class _FakeScalars:
    def __init__(self, items):
        self._items = items

    def first(self):
        return self._items[0] if self._items else None

    def all(self):
        return list(self._items)


class _FakeResult:
    def __init__(self, items=None):
        self._items = items or []

    def scalars(self):
        return _FakeScalars(self._items)


class _FakeDB:
    def __init__(self, results):
        self._results = list(results)
        self.flushed = False

    async def execute(self, stmt):
        if self._results:
            return self._results.pop(0)
        return _FakeResult([])

    async def flush(self):
        self.flushed = True


class _Student:
    def __init__(self, course_type="introductory"):
        self.id = uuid.uuid4()
        self.user_id = uuid.uuid4()
        self.course_type = course_type
        self.extra_data = {}


class _Actor:
    id = uuid.uuid4()
    role = "staff"


@pytest.mark.asyncio
async def test_change_course_type_noop_same_value(monkeypatch):
    student = _Student("introductory")
    db = _FakeDB([])
    svc = StudentService(db)
    out = await svc.change_registration_course_type(student, "introductory", _Actor())
    assert out["changed"] is False


@pytest.mark.asyncio
async def test_change_course_type_blocks_when_registration_completed(monkeypatch):
    student = _Student("introductory")

    class _CompletedInst:
        is_completed = True

    db = _FakeDB([_FakeResult([_CompletedInst()])])
    svc = StudentService(db)
    with pytest.raises(ValueError, match="تکمیل"):
        await svc.change_registration_course_type(student, "comprehensive", _Actor())


@pytest.mark.asyncio
async def test_change_course_type_cancels_old_process(monkeypatch):
    student = _Student("introductory")

    class _ActiveInst:
        def __init__(self):
            self.id = uuid.uuid4()
            self.is_completed = False
            self.is_cancelled = False

    active = _ActiveInst()
    db = _FakeDB([
        _FakeResult([]),  # no completed registration
        _FakeResult([active]),  # active old process
    ])
    svc = StudentService(db)
    monkeypatch.setattr("app.services.student_service.flag_modified", lambda *a, **k: None)

    async def _noop_path(*_a, **_k):
        return False

    monkeypatch.setattr(svc, "ensure_primary_registration_path", _noop_path)

    out = await svc.change_registration_course_type(student, "comprehensive", _Actor(), reason="test")
    assert out["changed"] is True
    assert student.course_type == "comprehensive"
    assert active.is_cancelled is True
    assert str(active.id) in out["cancelled_instance_ids"]
    assert EXPECTED_REGISTRATION_CODE["comprehensive"] == "comprehensive_course_registration"
