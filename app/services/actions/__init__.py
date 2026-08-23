"""Domain modules that make up ActionHandler.

Each module contributes a mixin of `_handle_*` methods plus a REGISTRY mapping
action types to them. ActionHandler composes the mixins and merges the
registries, so a new action touches one domain module instead of a 5000-line
file. scripts/validate_action_coverage.py keeps the registry honest.
"""
