"""Explicit storage4 authority composition, with unchanged V3 provider transport."""
from neuron.effect_authority_v3 import ReconciliationRequiredV3
from neuron.effect_authority_v4 import PostgresEffectAuthorityV4
from neuron.effect_coordinator_v3 import ObjectEffectCoordinatorV3
from neuron.effect_protocol_v3 import ObjectFenceV3

class ObjectEffectCoordinatorV4(ObjectEffectCoordinatorV3):
 _authority_class=PostgresEffectAuthorityV4
 def renew(self,scope):
  update=self.authority.prepare_renewal(scope)
  fence=ObjectFenceV3.from_context(scope.template,scope.fencing_token)
  try:ack=self.transport.advance_fence(fence,update)
  except Exception:raise ReconciliationRequiredV3('successor fence outcome unknown; lookup exact retained update') from None
  self.authority.activate_scope(scope.scope_id,ack)
  return ack
