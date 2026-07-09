import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'

export default defineConfig({
  plugins: [react()],
  build: {
    lib: {
      entry: resolve(__dirname, 'src/embed.ts'),
      name: 'GaplyWidget',
      fileName: 'embed',
      formats: ['iife']
    },
    rollupOptions: {
      // For a standalone embed, we bundle React and ReactDOM inside the script.
      external: [], 
      output: {
        extend: true
      }
    }
  },
  define: {
    'process.env.NODE_ENV': '"production"'
  }
})
