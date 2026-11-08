# F04-R5 implementation record

Status: BLOCKED. Local implementation evidence only; independent acceptance is not claimed.

Prerequisites: R4 package SHA256SUMS 443a4d7f6098f63822bf07980aacde79215e985abebf4ff1c3abcb4cb6ccbb74; R3 package SHA256SUMS 48cff179270ffaa8e1f3bf7610d638eb73e396584d2f656b31979d183c0faaf8.

Scoped changes: owner-signed minting; direct DID/owner datum binding; bootstrap equality; trusted authority anchors; non-self-referential static RegistryAuthorityPayloadV1 projection; registry-script/datum/owner-linked burn; registration value conservation; seven-parameter pinned-Aiken blueprint.

Fresh checks: pinned Aiken check --skip-tests exit 0; disposable full-copy pinned build exit 0; migration tests 15/15; design R5 tests 6/6.

Evaluator blocker: the frozen 49-row matrix contains labels only, not reviewed serialized datum/redeemer/transaction/reference-input/value/ScriptContext fixtures. Register/update/deregister rows need distinct exact topologies and slash rows need typed pre-F05 contexts. Inventing fixtures would make expected behavior self-authored. No evaluator or mutation files were created and no rows are claimed executed.

The canonical lockfile was already dirty before this slice; pinned Aiken refreshes volatile etags during checks. Its pre-slice bytes could not be reconstructed from accepted packages, so provenance continuity is not claimed.

F04=REVALIDATED_OPEN; F01-F05 unchanged; M3=OPEN; Deposit and ExecuteIntent disabled; Pre-Prod admission INCONCLUSIVE; promotion NOT READY. INV-1 through INV-10 and mock behavior unchanged.
