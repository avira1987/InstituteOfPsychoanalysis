"""Guards for the declarative inter-process wiring layer.

These tests need no database: they exercise the wiring file, the link matcher
and the dispatcher in isolation.
"""

import uuid

import pytest

from app.core.chaining import (
    ChainingContext,
    dispatch_chaining,
    registered_handler_names,
)
from app.core.wiring_registry import (
    PHASE_AFTER_TRANSITION,
    PHASE_ON_START,
    WiringConfigError,
    WiringRegistry,
    get_registry,
    parse_links,
)

# Every (phase, process_code) pair that used to be a hardcoded `if` block in
# StateMachineEngine. If a link is deleted or renamed without replacement, this
# is the test that fails.
EXPECTED_COVERAGE = {
    PHASE_ON_START: {
        "therapy_changes",
        "educational_leave",
        "full_education_leave",
        "therapy_completion",
        "ta_to_assistant_faculty",
        "return_to_full_education",
        "introductory_term_end",
    },
    PHASE_AFTER_TRANSITION: {
        "introductory_course_registration",
        "lesson_start_per_term",
        "ta_track_change",
        "start_therapy",
        "return_to_full_education",
        "full_education_leave",
        "session_payment",
        "therapy_completion",
        "therapy_changes",
        "student_non_registration",
        "intern_bulk_patient_referral",
        "ta_to_assistant_faculty",
        "upgrade_to_ta",
        "comprehensive_term_start",
        "intro_second_semester_registration",
    },
}


def test_wiring_file_parses():
    registry = get_registry()
    assert registry.links, "metadata/wiring/process_links.json produced no links"


def test_every_declared_handler_is_registered():
    missing = sorted(get_registry().handler_names() - registered_handler_names())
    assert not missing, f"wiring references unregistered handlers: {missing}"


def test_no_orphan_handlers():
    """A handler nobody wires up is dead code that silently never runs."""
    orphans = sorted(registered_handler_names() - get_registry().handler_names())
    assert not orphans, f"registered handlers absent from the wiring file: {orphans}"


@pytest.mark.parametrize("phase", sorted(EXPECTED_COVERAGE))
def test_legacy_hardcoded_hooks_still_covered(phase):
    covered = {
        code for link in get_registry().links if link.phase == phase for code in link.from_process
    }
    missing = sorted(EXPECTED_COVERAGE[phase] - covered)
    assert not missing, f"processes lost their {phase} wiring: {missing}"


def test_on_start_links_have_no_transition_matchers():
    for link in get_registry().links:
        if link.phase == PHASE_ON_START:
            assert link.to_state is None and link.trigger is None and link.from_state is None


def test_link_ids_are_unique():
    links = get_registry().links
    assert len({link.id for link in links}) == len(links)


def test_duplicate_link_id_is_rejected():
    payload = {
        "links": [
            {"id": "dup", "phase": PHASE_ON_START, "from_process": "a", "handler": "h"},
            {"id": "dup", "phase": PHASE_ON_START, "from_process": "b", "handler": "h"},
        ]
    }
    with pytest.raises(WiringConfigError, match="duplicate link id"):
        parse_links(payload)


def test_unknown_phase_is_rejected():
    payload = {"links": [{"id": "x", "phase": "whenever", "from_process": "a", "handler": "h"}]}
    with pytest.raises(WiringConfigError, match="phase"):
        parse_links(payload)


def test_on_start_link_with_to_state_is_rejected():
    payload = {
        "links": [
            {
                "id": "x",
                "phase": PHASE_ON_START,
                "from_process": "a",
                "handler": "h",
                "to_state": "s",
            }
        ]
    }
    with pytest.raises(WiringConfigError, match="meaningless for phase 'on_start'"):
        parse_links(payload)


# ─── matcher semantics ──────────────────────────────────────────────


def _registry(*raw_links) -> WiringRegistry:
    return WiringRegistry(parse_links({"links": list(raw_links)}))


def test_requires_completed_filters_incomplete_instances():
    registry = _registry(
        {
            "id": "only_when_done",
            "phase": PHASE_AFTER_TRANSITION,
            "from_process": "p",
            "to_state": "done",
            "requires_completed": True,
            "handler": "h",
        }
    )
    common = dict(phase=PHASE_AFTER_TRANSITION, process_code="p", to_state="done")
    assert registry.links_for(**common, is_completed=True)
    assert not registry.links_for(**common, is_completed=False)


def test_to_state_accepts_a_list():
    registry = _registry(
        {
            "id": "multi",
            "phase": PHASE_AFTER_TRANSITION,
            "from_process": "p",
            "to_state": ["a", "b"],
            "handler": "h",
        }
    )
    assert registry.links_for(phase=PHASE_AFTER_TRANSITION, process_code="p", to_state="a")
    assert registry.links_for(phase=PHASE_AFTER_TRANSITION, process_code="p", to_state="b")
    assert not registry.links_for(phase=PHASE_AFTER_TRANSITION, process_code="p", to_state="c")


def test_phases_do_not_leak_into_each_other():
    registry = _registry(
        {"id": "s", "phase": PHASE_ON_START, "from_process": "p", "handler": "h"},
    )
    assert registry.links_for(phase=PHASE_ON_START, process_code="p")
    assert not registry.links_for(phase=PHASE_AFTER_TRANSITION, process_code="p")


def test_disabled_link_never_matches():
    registry = _registry(
        {
            "id": "off",
            "phase": PHASE_ON_START,
            "from_process": "p",
            "handler": "h",
            "enabled": False,
        }
    )
    assert not registry.links_for(phase=PHASE_ON_START, process_code="p")


def test_edges_expands_process_pairs():
    registry = _registry(
        {
            "id": "e",
            "phase": PHASE_ON_START,
            "from_process": ["a", "b"],
            "to_process": ["c"],
            "handler": "h",
        }
    )
    assert {(src, dst) for src, dst, _ in registry.edges()} == {("a", "c"), ("b", "c")}


# ─── dispatcher behaviour ───────────────────────────────────────────


class _FakeDb:
    def __init__(self):
        self.flushes = 0

    async def flush(self):
        self.flushes += 1


class _FakeInstance:
    def __init__(self, process_code="p", is_completed=False, tag="original"):
        self.id = uuid.uuid4()
        self.process_code = process_code
        self.student_id = uuid.uuid4()
        self.is_completed = is_completed
        self.tag = tag


class _FakeEngine:
    def __init__(self, refetched=None):
        self.refetched = refetched
        self.refetch_calls = 0

    async def get_process_instance(self, instance_id):
        self.refetch_calls += 1
        return self.refetched


def _ctx(db, engine, instance, phase=PHASE_AFTER_TRANSITION, **kw):
    return ChainingContext(
        db=db,
        engine=engine,
        instance=instance,
        process_code=instance.process_code,
        student_id=instance.student_id,
        actor_id=uuid.uuid4(),
        is_completed=instance.is_completed,
        phase=phase,
        **kw,
    )


@pytest.fixture
def isolated_registry(monkeypatch):
    """Swap the module-level registry for one built from inline links."""

    def _install(*raw_links):
        registry = _registry(*raw_links)
        monkeypatch.setattr("app.core.chaining.get_registry", lambda: registry)
        return registry

    return _install


@pytest.fixture
def temp_handlers(monkeypatch):
    """Register throwaway handlers without polluting the global table."""
    import app.core.chaining as chaining

    table = dict(chaining._HANDLERS)
    monkeypatch.setattr(chaining, "_HANDLERS", table)
    monkeypatch.setattr(chaining, "_handlers_loaded", True)
    return table


async def test_dispatch_runs_matching_links_in_order(isolated_registry, temp_handlers):
    calls = []
    temp_handlers["first"] = lambda ctx: _record(calls, "first")
    temp_handlers["second"] = lambda ctx: _record(calls, "second")
    isolated_registry(
        {"id": "a", "phase": PHASE_AFTER_TRANSITION, "from_process": "p", "handler": "first"},
        {"id": "b", "phase": PHASE_AFTER_TRANSITION, "from_process": "p", "handler": "second"},
    )

    await dispatch_chaining(_ctx(_FakeDb(), _FakeEngine(), _FakeInstance()))
    assert calls == ["first", "second"]


async def _record(sink, name):
    sink.append(name)


async def test_failing_link_does_not_stop_later_links(isolated_registry, temp_handlers):
    calls = []

    async def boom(ctx):
        raise RuntimeError("edge exploded")

    temp_handlers["boom"] = boom
    temp_handlers["after"] = lambda ctx: _record(calls, "after")
    isolated_registry(
        {"id": "a", "phase": PHASE_AFTER_TRANSITION, "from_process": "p", "handler": "boom"},
        {"id": "b", "phase": PHASE_AFTER_TRANSITION, "from_process": "p", "handler": "after"},
    )

    # No exception escapes: a broken edge must not roll back a done transition.
    await dispatch_chaining(_ctx(_FakeDb(), _FakeEngine(), _FakeInstance()))
    assert calls == ["after"]


async def test_unknown_handler_is_skipped_not_raised(isolated_registry, temp_handlers):
    isolated_registry(
        {"id": "a", "phase": PHASE_AFTER_TRANSITION, "from_process": "p", "handler": "nope"},
    )
    assert await dispatch_chaining(_ctx(_FakeDb(), _FakeEngine(), _FakeInstance())) is None


async def test_flush_before_flushes_the_session(isolated_registry, temp_handlers):
    db = _FakeDb()
    temp_handlers["noop"] = lambda ctx: _record([], "noop")
    isolated_registry(
        {
            "id": "a",
            "phase": PHASE_ON_START,
            "from_process": "p",
            "handler": "noop",
            "flush_before": True,
        },
    )

    await dispatch_chaining(_ctx(db, _FakeEngine(), _FakeInstance(), phase=PHASE_ON_START))
    assert db.flushes == 1


async def test_refetch_instance_returns_fresh_instance(isolated_registry, temp_handlers):
    fresh = _FakeInstance(tag="fresh")
    engine = _FakeEngine(refetched=fresh)
    temp_handlers["noop"] = lambda ctx: _record([], "noop")
    isolated_registry(
        {
            "id": "a",
            "phase": PHASE_AFTER_TRANSITION,
            "from_process": "p",
            "handler": "noop",
            "refetch_instance": True,
        },
    )

    result = await dispatch_chaining(_ctx(_FakeDb(), engine, _FakeInstance()))
    assert engine.refetch_calls == 1
    assert result is fresh


async def test_later_links_see_the_refetched_instance(isolated_registry, temp_handlers):
    fresh = _FakeInstance(tag="fresh")
    seen = []

    async def observe(ctx):
        seen.append(ctx.instance.tag)

    temp_handlers["noop"] = lambda ctx: _record([], "noop")
    temp_handlers["observe"] = observe
    isolated_registry(
        {
            "id": "a",
            "phase": PHASE_AFTER_TRANSITION,
            "from_process": "p",
            "handler": "noop",
            "refetch_instance": True,
        },
        {"id": "b", "phase": PHASE_AFTER_TRANSITION, "from_process": "p", "handler": "observe"},
    )

    await dispatch_chaining(_ctx(_FakeDb(), _FakeEngine(refetched=fresh), _FakeInstance()))
    assert seen == ["fresh"]


async def test_no_matching_links_is_a_cheap_noop(isolated_registry, temp_handlers):
    isolated_registry(
        {"id": "a", "phase": PHASE_AFTER_TRANSITION, "from_process": "other", "handler": "x"},
    )
    assert await dispatch_chaining(_ctx(_FakeDb(), _FakeEngine(), _FakeInstance())) is None
