# M7 INV-2 post-payout cap policy decision, r1

Decision date: 2026-10-06
Scope: restricted faucet-only testnet remediation

## Owner decision

For this restricted testnet, a payout that would violate the existing 30% deployed-capital invariant must revert. An approved claim remains APPROVED and retryable after sufficient capital is returned or funding otherwise restores a permitted post-payout ratio. Possible payout delay is accepted.

For pre-payout total fund balance T, payout P, and currently recorded deployed amount D, execution requires:

D <= floor(3000 * (T - P) / 10000)

The cap basis remains totalFundBalance = liquid token balance + totalDeployedBalance. The payout must also be covered by available liquid token balance. Both checks occur before PAID state or token transfer. A failed check does not revoke or alter the approved claim. A token-transfer failure must roll back the PAID state with transaction atomicity.

## Accepted risk and implementation limits

The owner accepts that an approved claim can remain unpaid for an unbounded period if the fund cannot restore a permitted post-payout ratio. This decision does not forgive or reduce approved claims and does not introduce claim queues or expiry rules.

The current withdrawal accounting is not verified vault redemption. withdrawFromYield accepts a vault address but does not call that vault. It reduces totalDeployedBalance and pulls the requested token amount from the yield manager through safeTransferFrom. The vault address is emitted as event metadata. Tests that return principal through the yield manager establish only this local accounting path. No vault redemption, accrued yield, or guaranteed payout liveness is established by this decision.

## Explicit exclusions

Do not add automatic yield unwinding, change vault integrations, forgive claims, reduce payouts, add queues or expiry rules, create a privileged bypass, or relax the cap. Preserve claim amount and approval, governance, roles, proxy storage layout, and reentrancy protection. INV-9 is out of scope.

## Review and acceptance boundary

This is the recorded owner policy choice required before source edits. It authorizes only the narrow post-payout cap containment implementation and its focused tests. The policy record must receive independent review before production source is edited. Passing local tests can establish scoped post-payout containment only; it cannot establish vault redemption, payout liveness, INV-9, M5 completion, or testnet readiness.
