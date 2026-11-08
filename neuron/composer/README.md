# Resource Composition Engine (`neuron/composer/`)

`VAMSResourceComposer` currently scores candidates and creates local allocation
simulations. Provider execution, authenticated registry reads and execution
receipts are not implemented here. The default constructor permits pure pricing
helpers but rejects synthetic provisioning in every runtime mode.

Select `simulation=True` explicitly under a current `test`, `local` or `demo`
runtime policy for local planning. Staging, testnet and production reject it.
Every new catalogue resolution/provisioning operation checks the captured policy
and current effective registered mock flags. Configuration changes require a new
valid instance. Collaborator callbacks are rechecked before publishing a plan.

`provision*` returns `AllocationStatus.SIMULATED`, never ACTIVE. Serialized records
are marked non-authoritative and have no escrow transaction. `list_instances()`
includes simulations; `list_active_instances()` filters ACTIVE only. Local
inspection/removal works after runtime drift; `deprovision` only removes a
simulation and neither releases a provider resource nor pays a claim. Simulation
counters are separate; real provisioning/deprovisioning/active counters stay zero.

Pure scoring, allocation and price quotes remain local utilities. Quotes use the
allocator's actual assignments/allocated units, retain legacy quote-only inputs,
and remain `authoritative: false`, `transactionReady: false`. Transaction building
requires the separate typed settlement interface, integer token units and authentic
registry terms. Simulations cannot supply execution proof.

Gateway enables this simulation only during validated demo startup. Other modes
return unavailable for composition and synthetic Service Block/macro catalogues;
unrelated Gateway routes remain available. Static blueprint templates are clearly
labelled planning metadata. Existing privileged/read authentication is preserved.

See `docs/remediation/repair_20261101/COMPOSER-SIMULATION-BOUNDARY.md` for evidence
and outstanding implementation/qualification requirements for both chains.
