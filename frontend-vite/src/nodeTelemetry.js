export const NODE_TELEMETRY_MESSAGE =
  'Live node telemetry requires an authenticated server-side session.';

const UNAVAILABLE_NODE_TELEMETRY = Object.freeze({
  status: 'unavailable',
  requested: false,
  authoritative: false,
  simulated: false,
  nodes: Object.freeze([]),
  message: NODE_TELEMETRY_MESSAGE,
});

export function resolveBrowserNodeTelemetry(gatewayOutcome = undefined) {
  // The browser has no M2 signing authority. Gateway outcomes must never be
  // reinterpreted as live or simulated telemetry by this static SPA.
  void gatewayOutcome;
  return UNAVAILABLE_NODE_TELEMETRY;
}
