"""Reference interval arithmetic only; no Aiken, signatures, ledger or effects.

Keep the historical scalar byte oracle intact. New queue callers must validate
the complete supported Plutus V3 interval before selecting its upper bound.
"""
from dataclasses import dataclass

from ..repair_20261028.governance_contract import (
    ContractError, DELAY_MS, LIFETIME_MS, digest, intent_preimage, proposal_preimage, queue_intent,
)

U64_MAX = (1 << 64) - 1
MAX_WIDTH_MS = 300_000


def timestamp(value):
    if type(value) is not int or not 0 <= value <= U64_MAX:
        raise ContractError('finite unsigned 64-bit millisecond timestamp required')
    return value


@dataclass(frozen=True)
class ValidityWindow:
    lower: int
    upper: int
    lower_inclusive: bool = True
    upper_inclusive: bool = False

    def validate(self):
        timestamp(self.lower)
        timestamp(self.upper)
        if self.lower_inclusive is not True or self.upper_inclusive is not False:
            raise ContractError('supported interval must be [lower, upper)')
        if not 0 < self.upper - self.lower <= MAX_WIDTH_MS:
            raise ContractError('nonempty interval no wider than five minutes required')


def entirely_before(window, deadline):
    window.validate()
    timestamp(deadline)
    return window.lower < deadline and window.upper <= deadline


def entirely_at_or_after(window, deadline):
    window.validate()
    timestamp(deadline)
    return window.lower >= deadline


def queue_for_window(config, proposal, window):
    window.validate()
    if digest(proposal_preimage(config, proposal)) != proposal.asset:
        raise ContractError('proposal asset does not bind current registered terms')
    if not entirely_at_or_after(window, proposal.deadline):
        raise ContractError('entire queue interval must follow the voting deadline')
    timestamp(window.upper + DELAY_MS + LIFETIME_MS)
    intent = queue_intent(config, proposal, window.upper)
    # Validate the existing byte/delay/identity constraints too. This reference
    # function grants no authority, creates no transaction and signs nothing.
    intent_preimage(config, intent)
    return intent


def expiry_allowed(intent, window):
    timestamp(intent.execute_after + intent.lifetime)
    return entirely_at_or_after(window, intent.execute_after + intent.lifetime)
