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
  primaryColor: 'blue',
  fontFamily: 'Arial, Helvetica, sans-serif',
  defaultRadius: 'xs',
  colors: {
    dark: ['#eeeeee', '#d4d4d4', '#b5b5b5', '#9d9d9d', '#747474', '#4b4b4b', '#3c3c3c', '#313131', '#252526', '#1f1f1f'],
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
