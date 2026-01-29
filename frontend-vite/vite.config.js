import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
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
})
