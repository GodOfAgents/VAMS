import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import crypto from 'crypto'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const configuredGateway = new URL(
    env.VITE_VAMS_GATEWAY_URL || (mode === 'development'
      ? 'http://localhost:8000'
      : 'https://gateway.vams.network')
  )
  if (mode !== 'development' && configuredGateway.protocol !== 'https:') {
    throw new Error('VITE_VAMS_GATEWAY_URL must use HTTPS outside development')
  }
  if (
    configuredGateway.username ||
    configuredGateway.password ||
    configuredGateway.pathname !== '/' ||
    configuredGateway.search ||
    configuredGateway.hash
  ) {
    throw new Error('VITE_VAMS_GATEWAY_URL must be an origin without credentials or query data')
  }
  const gatewayOrigin = configuredGateway.origin
  const csp = [
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data:",
    "font-src 'self'",
    `connect-src 'self' ${gatewayOrigin}`,
    "object-src 'none'",
    "base-uri 'self'",
    "frame-ancestors 'none'",
    "form-action 'self'",
  ].join('; ')

  return {
    plugins: [
      react(),
      {
        name: 'vite-plugin-sri-custom',
        transformIndexHtml(html, ctx) {
          if (!ctx.bundle) return html
          let newHtml = html
          for (const [fileName, asset] of Object.entries(ctx.bundle)) {
            if (fileName.endsWith('.js') || fileName.endsWith('.css')) {
              const content = asset.type === 'asset' ? asset.source : asset.code
              const hash = crypto.createHash('sha384').update(content).digest('base64')
              const integrity = `sha384-${hash}`

              const escapedFileName = fileName.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&')
              const scriptRegex = new RegExp(`(<script[^>]+src=["'][^"']*?${escapedFileName}["'])([^>]*>)`, 'g')
              const cssRegex = new RegExp(`(<link[^>]+href=["'][^"']*?${escapedFileName}["'])([^>]*>)`, 'g')

              newHtml = newHtml.replace(scriptRegex, `$1 integrity="${integrity}"$2`)
              newHtml = newHtml.replace(cssRegex, `$1 integrity="${integrity}"$2`)
            }
          }
          return newHtml
        }
      }
    ],
    server: {
      headers: {
        'Content-Security-Policy': csp,
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains; preload',
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Referrer-Policy': 'strict-origin-when-cross-origin'
      }
    },
    preview: {
      headers: {
        'Content-Security-Policy': csp,
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains; preload',
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Referrer-Policy': 'strict-origin-when-cross-origin'
      }
    },
    build: {
      // Minification target for smaller bundles
      target: 'esnext',
      // Enable minification
      minify: 'esbuild',
      // Code-splitting for Three.js (separate chunk)
      rollupOptions: {
        output: {
          manualChunks: {
            // Separate Three.js into its own chunk for better caching
            three: ['three'],
            // React core
            vendor: ['react', 'react-dom'],
          },
        },
      },
      // Reduce chunk size warnings
      chunkSizeWarningLimit: 500,
    },
    // Optimize dependencies
    optimizeDeps: {
      include: ['react', 'react-dom', 'three'],
    },
  }
})
