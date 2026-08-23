import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: '../src/ptcgp_deck2qr/webgui',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        entryFileNames: 'app.js',
        chunkFileNames: 'chunks/[name]-[hash].js',
        assetFileNames: assetInfo =>
          assetInfo.names?.some(name => name.endsWith('.css'))
            ? 'app.css'
            : 'assets/[name]-[hash][extname]',
      },
    },
  },
});
