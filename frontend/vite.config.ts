import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '');
  const backendTarget = env.VITE_BACKEND_PROXY_TARGET || 'http://localhost:8000';

  return {
    plugins: [react()],
    base: './',
    server: {
      host: '0.0.0.0',
      port: 5173,
      proxy: {
        '/ws': {
          target: backendTarget,
          changeOrigin: true,
          ws: true,
        },
        '/api': {
          target: backendTarget,
          changeOrigin: true,
        },
        '/snapshots': {
          target: backendTarget,
          changeOrigin: true,
        },
        '/camera-areas': {
          target: backendTarget,
          changeOrigin: true,
        },
        '/health': {
          target: backendTarget,
          changeOrigin: true,
        },
      },
    },
  };
});
