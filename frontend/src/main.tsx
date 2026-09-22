import React from 'react';
import ReactDOM from 'react-dom/client';
import { MantineProvider, createTheme } from '@mantine/core';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import '@mantine/core/styles.css';
import 'maplibre-gl/dist/maplibre-gl.css';
import './styles.css';
import { App } from './App';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: Number.POSITIVE_INFINITY, retry: 2, refetchOnWindowFocus: false },
  },
});

const theme = createTheme({
  primaryColor: 'cyan',
  fontFamily: 'Inter, Manrope, system-ui, sans-serif',
  defaultRadius: 'md',
  colors: {
    dark: ['#d7dee8', '#aeb9c8', '#8592a5', '#5e6c80', '#3f4d61', '#29384b', '#1b293a', '#111d2b', '#0b1521', '#07101a'],
  },
});

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <MantineProvider theme={theme} defaultColorScheme="dark">
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </MantineProvider>
  </React.StrictMode>,
);

