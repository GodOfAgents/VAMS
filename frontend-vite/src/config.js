const LOCAL_GATEWAY_URL = 'http://localhost:8000'
const TESTNET_GATEWAY_URL = 'https://gateway.vams.network'

function resolveGatewayUrl() {
  const configured = import.meta.env.VITE_VAMS_GATEWAY_URL?.trim()
  const candidate = configured || (import.meta.env.PROD ? TESTNET_GATEWAY_URL : LOCAL_GATEWAY_URL)
  const parsed = new URL(candidate)

  if (import.meta.env.PROD && parsed.protocol !== 'https:') {
    throw new Error('VITE_VAMS_GATEWAY_URL must use HTTPS in production builds')
  }
  if (
    parsed.username ||
    parsed.password ||
    parsed.pathname !== '/' ||
    parsed.search ||
    parsed.hash
  ) {
    throw new Error('VITE_VAMS_GATEWAY_URL must be an origin without credentials or query data')
  }

  return parsed.origin
}

export const GATEWAY_ORIGIN = resolveGatewayUrl()
export const TESTNET_CAPABILITIES = Object.freeze({
  readOnly: true,
  walletTransactions: false,
  realFiat: false,
  realYieldCapital: false,
})
