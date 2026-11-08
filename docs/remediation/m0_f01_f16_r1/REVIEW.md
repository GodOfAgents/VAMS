# M0 F01-F16 current-source review

Date: 2026-09-22  
Superproject HEAD: `829ab544571f12efe50ecb5740f129c8acb3e16f`  
Scope: classification only; no later-milestone repair or promotion

## Result

All sixteen findings were reproduced or otherwise confirmed as current gaps
and are now `REVALIDATED_OPEN`. This satisfies M0's truthful-classification
requirement without falsely treating later remediation acceptance criteria as
M0 work.

| Slice | Findings | Result |
|---|---|---|
| Cardano authority/bridge | F01-F05 | Revalidated open; assigned M3/M4. Aiken unavailable locally; native adversarial coverage remains part of M3. |
| Proof/runtime/settlement | F06-F13 | Revalidated open; assigned M1/M2/M4/M5/M6 as already planned. |
| Telemetry/provider/release | F14-F16 | Revalidated open; assigned M5-M9 as already planned. |

## Current-source hashes

```text
f9751165783a54c80d5bda2bda962f65010eb222954ff9033feef8c3690cc772  cardano/validators/insurance_fund.ak
222b2b7713fe9a81295db59b9b043d21f93664f8247b63fa28a003c13fc2e4ad  cardano/validators/timelock.ak
c8982b3bb5e82dca81df808b5d83430d81e7d9cccdcbc2179fa44474e50ab52b  cardano/validators/governor.ak
c9894be34383ec8b651d979e33bccda44c620c4f20596dd6587ac684dfa7b579  cardano/validators/agent_registry.ak
6df86d4549e9289734b80d2193cc77fffedcb856b46fe41e29d3d8134a8b7917  cardano/lib/vams/icb.ak
04787f553c472d1cbca314e8282a1f8dbeb00649bb0f23f080beb41f9506033f  neuron/bridge_executor.py
fa24f6b3c4b89543210c01d728e8ac226ebeef5694504fd3093f3f476fdbeb9f  contracts/src/trust/plugins/TEEProofPlugin.sol
b607a43d601275885aa63edb01803afe9094943de39f963b9f49fc6b8a227684  contracts/src/trust/plugins/ZKMLProofPlugin.sol
fb092c4a5c0f77441649ec455ed0c7ccb56ab538054ede046e64d08832cf9d54  contracts/src/economic/ComposedSettlement.sol
5684346ad2101ffe9477cfcbefcf13e7b606ba580b2bebd4cbb792754b8e0834  neuron/trust_plugins/tee_plugin.py
ccb8275f5fd7a3b6018b36f6d238d8a386d8caee3bd78dea81b5c9eaf1bc838d  neuron/runtime_safety.py
cffa5bbe65142ca7801a51b4f17d4a9b1c7fb8b125ffcb63337aa01df2b95b2c  gateway/server.py
5a4ededb6af5581dbe4e1565c34ec9b5edf9e7b421e313ce24d1d9ad708adf28  neuron/sdk/cognitive_drift.py
dad2d03a6a00612be1e474dd167e5103ad0d4970e87f4796193e5c988158225a  neuron/sentinel/world_state_fidelity.py
f1f45f06c792f2ebba159ae08481cbaf5d323218ea0214cac6d32b7864905444  neuron/workflows.py
494247b4459dfece4431559c82cc0b1a9b6123eb6f5c16e66dfbc45bb7c781b4  neuron/sdk/interrupt_handler.py
c1651fade1e16fdbfb97508a21027bc930a94567a5c6fa72ed1635c60498ca8b  neuron/intelligence/anomaly_detector.py
601f64624ab0dc44ef2d2e24fba0c4a3c78d9e67b5474f375162f0e1bf14337e  neuron/compute.py
22d9ee24094de3fc89ccf68dfe36308e9110505d7666ee52c9f52b9d58a89317  neuron/providers.py
1e42daeb3ed88664cd56192f4bb010176c5a428cdc3747f4f0479f014ed20846  neuron/composer/scorer.py
9fd7e0ebfcf6caa6916524f98d4f926989b8906effdc071e992dd2493a595245  scripts/audit/audit_program.py
```

## Focused verification

The pinned Python 3.12 environment ran fourteen current focused test files
covering trust plugins, gateway auth, runtime safety, DA boundaries, world
state, workflows, composed settlement, anomaly detection, performance audit,
and composer allocation/scoring.

Result: **174 passed in 35.25s**, exit 0, no timeout. Source HEAD/tree and dirty
state were unchanged across the run.

- evidence directory:
  `/home/GodOfAgents/vams-evidence/m0-20260909/20260921T201118Z-f1b815ba-m0-f06-f15-current-focused`
- record SHA-256:
  `82144906d708ca17633062ab38789e425074611154ea54e25bcab98eaae74fc6`
- log SHA-256:
  `397eaad80cf85cb9d4536b751d54a41e6af46fcb82fd4ba2aa39a47a6f3f8d45`

No dependency was installed. No vendor, contract, validator, runtime, mock-mode,
invariant, deployment, or promotion behavior was changed.
