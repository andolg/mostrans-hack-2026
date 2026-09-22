import { useEffect, useMemo, useState } from 'react';
import { Alert, AppShell, Box, Burger, Button, Center, Drawer, Group, Loader, Text } from '@mantine/core';
import { useDisclosure, useMediaQuery } from '@mantine/hooks';
import { useQuery } from '@tanstack/react-query';
import { IconAlertCircle, IconAdjustmentsHorizontal } from '@tabler/icons-react';
import { Brand } from './components/Brand';
import { StatusBadge } from './components/StatusBadge';
import { forecastRepository } from './data/repository';
import type { ForecastHorizon, ForecastMetric } from './domain/types';
import { ForecastControls } from './features/filters/ForecastControls';
import { ForecastMap } from './features/map/ForecastMap';
import { ForecastChart } from './features/charts/ForecastChart';

export function App() {
  const compact = useMediaQuery('(max-width: 900px)');
  const [drawerOpened, drawer] = useDisclosure(false);
  const [horizon, setHorizon] = useState<ForecastHorizon>('day');
  const [metric, setMetric] = useState<ForecastMetric>('load');
  const [selectedRouteId, setSelectedRouteId] = useState<string | null>(null);
  const [selectedStopId, setSelectedStopId] = useState<string | null>(null);
  const [timeIndex, setTimeIndex] = useState(32);
  const [isPlaying, setIsPlaying] = useState(false);

  const geometryQuery = useQuery({
    queryKey: ['geometry'],
    queryFn: async () => {
      const [routes, stops, metadata, routeList] = await Promise.all([
        forecastRepository.getRouteGeometry(),
        forecastRepository.getStopGeometry(),
        forecastRepository.getOsmMetadata(),
        forecastRepository.getRoutes(),
      ]);
      return { routes, stops, metadata, routeList };
    },
  });

  const timelineRouteId = selectedRouteId ?? geometryQuery.data?.routeList[0]?.routeId;
  const timelineQuery = useQuery({
    queryKey: ['route-forecast', timelineRouteId, horizon],
    queryFn: () => forecastRepository.getRouteForecast(timelineRouteId!, horizon),
    enabled: Boolean(timelineRouteId),
  });
  const timeline = timelineQuery.data?.points ?? [];
  const safeIndex = Math.min(timeIndex, Math.max(0, timeline.length - 1));
  const timestamp = timeline[safeIndex]?.timestamp;

  const snapshotQuery = useQuery({
    queryKey: ['snapshot', timestamp, horizon],
    queryFn: () => forecastRepository.getNetworkSnapshot(timestamp!, horizon),
    enabled: Boolean(timestamp),
  });

  const stopForecastQuery = useQuery({
    queryKey: ['stop-forecast', selectedStopId, horizon],
    queryFn: () => forecastRepository.getStopForecast(selectedStopId!, horizon),
    enabled: Boolean(selectedStopId),
  });

  useEffect(() => {
    if (!isPlaying || timeline.length < 2) return;
    const timer = window.setInterval(() => setTimeIndex((value) => (value + 1) % timeline.length), 850);
    return () => window.clearInterval(timer);
  }, [isPlaying, timeline.length]);

  useEffect(() => {
    setTimeIndex(horizon === 'day' ? 32 : 0);
    setIsPlaying(false);
  }, [horizon]);

  const selectedStop = geometryQuery.data?.stops.features.find((feature) => feature.properties.stopId === selectedStopId);
  const selectedRoute = geometryQuery.data?.routeList.find((route) => route.routeId === timelineRouteId);
  const chartPoints = selectedStopId ? (stopForecastQuery.data?.points ?? []) : timeline;
  const chartTitle = selectedStop
    ? `Остановка «${selectedStop.properties.name}» · прогноз посадок`
    : `Маршрут ${selectedRoute?.routeRef ?? '—'} · оценочная загрузка`;

  const controls = useMemo(() => (
    <ForecastControls
      horizon={horizon}
      onHorizonChange={setHorizon}
      metric={metric}
      onMetricChange={setMetric}
      routes={geometryQuery.data?.routeList ?? []}
      selectedRouteId={selectedRouteId}
      onRouteChange={(routeId) => { setSelectedRouteId(routeId); setSelectedStopId(null); }}
      points={timeline}
      timeIndex={safeIndex}
      onTimeIndexChange={setTimeIndex}
      isPlaying={isPlaying}
      onPlayingChange={setIsPlaying}
      onDemo={() => {
        const demoRoute = geometryQuery.data?.routeList[0]?.routeId ?? null;
        setHorizon('day'); setSelectedRouteId(demoRoute); setSelectedStopId(null); setTimeIndex(33); setIsPlaying(true); drawer.close();
      }}
    />
  ), [horizon, metric, geometryQuery.data?.routeList, selectedRouteId, timeline, safeIndex, isPlaying, drawer]);

  const error = geometryQuery.error ?? timelineQuery.error ?? snapshotQuery.error;

  return (
    <AppShell header={{ height: 64 }} navbar={compact ? undefined : { width: 292, breakpoint: 'sm' }} padding={0}>
      <AppShell.Header className="topbar">
        <Group h="100%" px="lg" justify="space-between" wrap="nowrap">
          <Group wrap="nowrap">
            {compact && <Burger opened={drawerOpened} onClick={drawer.toggle} size="sm" />}
            <Brand />
          </Group>
          <Group wrap="nowrap">
            {!compact && <Text size="xs" c="dimmed">Москва · локальные данные OSM</Text>}
            <StatusBadge generatedAt={geometryQuery.data?.metadata.generatedAt} />
          </Group>
        </Group>
      </AppShell.Header>

      {!compact && <AppShell.Navbar className="filters-panel" p="lg">{controls}</AppShell.Navbar>}
      <Drawer opened={drawerOpened} onClose={drawer.close} title="Параметры прогноза" size="xs">
        {controls}
      </Drawer>

      <AppShell.Main className="dashboard-main">
        {error ? (
          <Center h="100%">
            <Alert icon={<IconAlertCircle size={18} />} title="Не удалось загрузить данные" color="red" maw={520}>
              <Text size="sm" mb="sm">{error instanceof Error ? error.message : 'Неизвестная ошибка'}</Text>
              <Button size="xs" variant="light" onClick={() => window.location.reload()}>Повторить</Button>
            </Alert>
          </Center>
        ) : geometryQuery.isLoading ? (
          <Center h="100%"><Loader color="cyan" /><Text ml="md" c="dimmed">Загружаем трамвайную сеть…</Text></Center>
        ) : geometryQuery.data ? (
          <Box className="workspace">
            {compact && (
              <Button className="floating-filter" leftSection={<IconAdjustmentsHorizontal size={16} />} onClick={drawer.open}>
                Фильтры
              </Button>
            )}
            <Box className="map-area">
              <ForecastMap
                routes={geometryQuery.data.routes}
                stops={geometryQuery.data.stops}
                snapshot={snapshotQuery.data}
                metric={metric}
                selectedRouteId={selectedRouteId}
                selectedStopId={selectedStopId}
                timestamp={timestamp}
                onSelectRoute={(routeId) => { setSelectedRouteId(routeId); setSelectedStopId(null); }}
                onSelectStop={(stopId) => setSelectedStopId(stopId)}
              />
              {snapshotQuery.isFetching && <div className="snapshot-loader"><Loader size="xs" color="cyan" /></div>}
            </Box>
            <ForecastChart
              points={chartPoints}
              metric={selectedStopId ? 'boardings' : metric}
              horizon={horizon}
              selectedIndex={safeIndex}
              title={chartTitle}
              loading={timelineQuery.isLoading || stopForecastQuery.isLoading}
            />
          </Box>
        ) : null}
      </AppShell.Main>
    </AppShell>
  );
}

