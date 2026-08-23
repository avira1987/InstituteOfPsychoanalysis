"""The action registry is assembled from per-domain modules; keep it coherent.

`ActionHandler` used to be one 5000-line module. Now each domain in
`app/services/actions/` contributes a mixin plus a REGISTRY, and ActionHandler
merges them. These tests catch the ways that assembly can silently go wrong:
a handler registered in two domains, a REGISTRY entry whose method is not on the
mixin, or a `@staticmethod` that lost its decorator during a move.
"""

import inspect

import pytest

from app.services.action_handler import ActionHandler
from app.services.actions import (
    attendance,
    notifications,
    payments,
    process_control,
    records,
    sessions,
    supervision,
    therapy,
)

DOMAIN_MODULES = [
    notifications,
    process_control,
    sessions,
    therapy,
    attendance,
    payments,
    supervision,
    records,
]


def test_registry_is_the_union_of_domain_registries():
    merged = {}
    for module in DOMAIN_MODULES:
        merged.update(module.REGISTRY)
    assert ActionHandler._registry == merged


def test_no_action_type_is_claimed_by_two_domains():
    seen: dict[str, str] = {}
    clashes = []
    for module in DOMAIN_MODULES:
        for action_type in module.REGISTRY:
            if action_type in seen:
                clashes.append(f"{action_type}: {seen[action_type]} and {module.__name__}")
            seen[action_type] = module.__name__
    assert not clashes, "action types registered in more than one domain: " + "; ".join(clashes)


@pytest.mark.parametrize("module", DOMAIN_MODULES, ids=lambda m: m.__name__.rsplit(".", 1)[-1])
def test_every_registry_entry_is_reachable_on_the_handler(module):
    """A REGISTRY value must be the same object ActionHandler exposes by name."""
    for action_type, handler in module.REGISTRY.items():
        name = handler.__name__
        assert hasattr(ActionHandler, name), f"{action_type} -> {name} missing on ActionHandler"
        assert getattr(ActionHandler, name) is handler, (
            f"{action_type} -> {name} resolves to a different object on ActionHandler; "
            "two domains probably define the same method name"
        )


def test_all_handlers_are_coroutines():
    """`_dispatch` awaits the handler, so a sync handler would fail at runtime."""
    offenders = [
        handler.__name__
        for handler in set(ActionHandler._registry.values())
        if not inspect.iscoroutinefunction(handler)
    ]
    assert not offenders, f"non-async action handlers: {offenders}"


def test_handlers_keep_the_dispatch_signature():
    """_dispatch calls handler(self, action, instance, context)."""
    wrong = []
    for handler in set(ActionHandler._registry.values()):
        params = list(inspect.signature(handler).parameters)
        if params[:4] != ["self", "action", "instance", "context"]:
            wrong.append(f"{handler.__name__}{tuple(params)}")
    assert not wrong, f"handlers with an unexpected signature: {wrong}"


def test_staticmethods_survived_the_split():
    """A lost @staticmethod silently turns `self` into the first real argument."""
    for owner, name in [
        (notifications.NotificationActionsMixin, "_record_sla_warning_dispatch"),
        (notifications.NotificationActionsMixin, "_format_committee_meeting_summary_fa"),
        (process_control.ProcessControlActionsMixin, "_notification_action_condition_matches"),
        (payments.PaymentActionsMixin, "_fee_ledger_category"),
    ]:
        assert isinstance(inspect.getattr_static(owner, name), staticmethod), (
            f"{owner.__name__}.{name} is no longer a staticmethod"
        )


def test_record_prefix_fallback_target_exists():
    """`_dispatch` routes unregistered record_* types to this handler."""
    assert hasattr(ActionHandler, "_handle_record_process_artifact")


def test_shared_helpers_stay_importable_from_action_handler():
    """Other modules import these from app.services.action_handler."""
    import app.services.action_handler as module

    for name in (
        "parse_therapy_session_id_list",
        "validate_therapy_reduction_preflight",
        "validate_supervision_reduction_preflight",
    ):
        assert callable(getattr(module, name, None)), f"{name} is no longer re-exported"
