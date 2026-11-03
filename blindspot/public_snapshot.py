"""Derived public study summary; scientific values stay unchanged."""
from copy import deepcopy


PRIVATE_PANEL_FIELDS={'token_budget_extension','estimated_credit_remaining'}


def public_summary(result):
    summary=deepcopy(result)
    for key in PRIVATE_PANEL_FIELDS:
        summary.pop(key,None)
    summary['public_snapshot_note']=(
        'Scientific metrics, counts, verdict examples and measured costs are unchanged. '
        'Personal remaining-credit estimates and the spending-authorisation record are omitted.'
    )
    return summary
