import { useEffect, useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import ReactECharts from 'echarts-for-react';
import type { EChartsType } from 'echarts';
import { Alert, Button, Loader, Select } from '@mantine/core';
import { getBoardings, getMetadata, getRoutes, getStops, exportUrl } from './data/api';
import type { BoardingPoint, Bucket } from './domain/types';
import { RouteMap } from './features/map/RouteMap';

const bucketLabels: Record<Bucket, string> = { hour: 'Час', day: 'День', month: 'Месяц' };
const number = new Intl.NumberFormat('ru-RU');

function nextMonth(date: string) {
  const [year, month] = date.slice(0, 7).split('-').map(Number);
  return new Date(Date.UTC(year, month, 1)).toISOString().slice(0, 10);
}

function slotKey(point: BoardingPoint) {
  return `${point.start}|${point.end}|${point.source}`;
}

function dateLabel(value: string, bucket: Bucket) {
  const [day, time] = value.split('T');
  if (bucket === 'month') return `${day.slice(5, 7)}.${day.slice(0, 4)}`;
  return bucket === 'hour' ? `${day.slice(8, 10)}.${day.slice(5, 7)} ${time.slice(0, 5)}` : `${day.slice(8, 10)}.${day.slice(5, 7)}`;
}

export function App() {
  const metadata = useQuery({ queryKey: ['metadata'], queryFn: getMetadata });
  const geometry = useQuery({
    queryKey: ['osm'],
    queryFn: async () => {
      const [routes, stops] = await Promise.all([getRoutes(), getStops()]);
      return { routes, stops };
    },
  });
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [bucket, setBucket] = useState<Bucket>('day');
  const [route, setRoute] = useState<number | null>(null);
  const [index, setIndex] = useState(0);

  useEffect(() => {
    if (!metadata.data) return;
    const from = nextMonth(metadata.data.historical_end);
    setStart(from);
    setEnd(nextMonth(from));
    setRoute(metadata.data.routes.includes(17) ? 17 : metadata.data.routes[0]);
  }, [metadata.data]);

  const periodError = !start || !end ? ''
    : start < (metadata.data?.historical_start ?? '') ? `История начинается ${metadata.data?.historical_start}. Выберите более позднее начало.`
      : start >= end ? 'Конец периода должен быть позже начала.' : '';
  const boardings = useQuery({
    queryKey: ['boardings', start, end, bucket],
    queryFn: () => getBoardings(start, end, bucket),
    enabled: Boolean(metadata.data && start && end && !periodError),
  });
  const points = boardings.data ?? [];
  const slots = useMemo(() => {
    const unique = new Map<string, BoardingPoint>();
    points.forEach((point) => unique.set(slotKey(point), point));
    return [...unique.values()].sort((a, b) => a.start.localeCompare(b.start));
  }, [points]);
  const safeIndex = Math.min(index, Math.max(slots.length - 1, 0));
  const active = slots[safeIndex];
  const snapshot = useMemo(() => points.filter((point) => active && slotKey(point) === slotKey(active)), [points, active]);
  const routePoints = useMemo(() => points.filter((point) => point.route === route).sort((a, b) => a.start.localeCompare(b.start)), [points, route]);
  const chartSelection = useRef({ routePoints, slots });
  chartSelection.current = { routePoints, slots };
  const activePoint = snapshot.find((point) => point.route === route);
  const mappedRoutes = useMemo(() => new Set(geometry.data?.routes.features.map((feature) => Number(feature.properties.routeRef)) ?? []), [geometry.data]);

  useEffect(() => setIndex(0), [start, end, bucket]);

  const chartOptions = useMemo(() => ({
    backgroundColor: 'transparent', animation: false,
    textStyle: { fontFamily: 'Arial, Helvetica, sans-serif' },
    grid: { left: 62, right: 18, top: 16, bottom: 42 },
    tooltip: {
      trigger: 'axis', backgroundColor: '#252526', borderColor: '#454545', textStyle: { color: '#d4d4d4' },
      formatter: (items: Array<{ dataIndex: number }>) => {
        const point = routePoints[items[0]?.dataIndex];
        return point ? `${dateLabel(point.start, bucket)}<br/>${point.source === 'actual' ? 'Факт' : 'Прогноз'}: ${number.format(point.boardings)} посадок` : '';
      },
    },
    xAxis: { type: 'category', data: routePoints.map((point) => dateLabel(point.start, bucket)), axisLabel: { color: '#9d9d9d', hideOverlap: true }, axisLine: { lineStyle: { color: '#4b4b4b' } }, axisTick: { show: false } },
    yAxis: { type: 'value', min: 0, axisLabel: { color: '#9d9d9d' }, splitLine: { lineStyle: { color: '#363636' } } },
    series: [{
      type: 'bar', barMaxWidth: 28, cursor: 'pointer',
      data: routePoints.map((point) => ({ value: point.boardings, itemStyle: { color: point.source === 'actual' ? '#7ca8cc' : '#c9a26b' } })),
      markLine: activePoint ? { symbol: 'none', silent: true, label: { show: false }, lineStyle: { color: '#e5e5e5', width: 1 }, data: [{ xAxis: routePoints.indexOf(activePoint) }] } : undefined,
    }],
  }), [routePoints, bucket, activePoint]);

  const onChartReady = (chart: EChartsType) => {
    chart.getZr().on('click', (event) => {
      const pixel = [event.offsetX, event.offsetY];
      if (!chart.containPixel({ gridIndex: 0 }, pixel)) return;
      const position = chart.convertFromPixel({ xAxisIndex: 0 }, event.offsetX);
      const point = chartSelection.current.routePoints[Math.round(Number(position))];
      if (!point) return;
      const selectedIndex = chartSelection.current.slots.findIndex((slot) => slotKey(slot) === slotKey(point));
      if (selectedIndex >= 0) setIndex(selectedIndex);
    });
  };

  const initialError = metadata.error ?? geometry.error;
  return (
    <div className="app">
      <header className="topbar"><strong>МосТрам</strong><span>Посадки на трамвайных маршрутах</span><span className="topbar-end">Москва</span></header>
      {initialError ? <div className="center"><Alert color="red" title="Не удалось загрузить данные">{String(initialError)}</Alert></div>
        : !metadata.data || !geometry.data ? <div className="center"><Loader size="sm" /> Загрузка данных…</div>
          : <div className="workspace">
            <aside className="sidebar">
              <div className="section-title">Параметры</div>
              <label className="field">Маршрут
                <Select aria-label="Маршрут" data={metadata.data.routes.map((value) => ({ value: String(value), label: `Трамвай ${value}` }))} value={route === null ? null : String(route)} onChange={(value) => setRoute(value === null ? null : Number(value))} searchable clearable={false} />
              </label>
              <div className="section-title section-gap">Период</div>
              <label className="field">Начало <input aria-label="Начало периода" type="date" value={start} onChange={(event) => setStart(event.target.value)} /></label>
              <label className="field">Конец, не включая дату <input aria-label="Конец периода" type="date" value={end} onChange={(event) => setEnd(event.target.value)} /></label>
              <label className="field">Шаг
                <Select aria-label="Шаг" data={Object.entries(bucketLabels).map(([value, label]) => ({ value, label }))} value={bucket} onChange={(value) => setBucket(value as Bucket || 'day')} />
              </label>
              {periodError && <Alert color="red" title="Некорректный период">{periodError}</Alert>}
              <div className="sidebar-note">Факт до {metadata.data.historical_end}. Дальше — прогноз. Предрасчёт до {metadata.data.precomputed_end}; более поздние даты рассчитываются по запросу.</div>
              {route !== null && !mappedRoutes.has(route) && <div className="sidebar-note">Геометрия маршрута {route} пока отсутствует в локальной OSM-выгрузке. Ряд и экспорт доступны.</div>}
              <Button component="a" href={exportUrl(start, end, bucket, route ?? undefined)} disabled={Boolean(periodError || !boardings.data)} variant="outline" size="sm" fullWidth>Скачать CSV</Button>
            </aside>
            <main className="main">
              <div className="map-panel">
                <RouteMap routes={geometry.data.routes} stops={geometry.data.stops} supportedRoutes={metadata.data.routes} points={points} snapshot={snapshot} selectedRoute={route} onSelectRoute={setRoute} />
                <div className="map-status">
                  {active ? <><b>{dateLabel(active.start, bucket)}</b><span>{bucketLabels[bucket].toLowerCase()} · {active.source === 'actual' ? 'факт' : 'прогноз'}</span>{route !== null && <strong>{activePoint ? `${number.format(activePoint.boardings)} посадок · маршрут ${route}` : 'Нет данных'}</strong>}</> : 'Выберите период'}
                </div>
                {boardings.isFetching && <div className="loading-chip"><Loader size="xs" /> Загрузка посадок…</div>}
                {boardings.error && !periodError && <div className="error-chip">Ошибка API: {String(boardings.error)}</div>}
              </div>
              <section className="timeline">
                <div className="timeline-top"><div><strong>{route === null ? 'Выберите маршрут' : `Маршрут ${route}`}</strong><span>Число посадок</span></div><div className="key"><i className="actual" /> Факт <i className="forecast" /> Прогноз</div></div>
                <div className="chart-wrap">{routePoints.length ? <ReactECharts option={chartOptions} onChartReady={onChartReady} style={{ height: '100%', width: '100%' }} /> : <div className="chart-empty">{periodError ? 'Исправьте период' : boardings.isLoading ? 'Загрузка ряда…' : 'Нет данных за выбранный период'}</div>}</div>
                <div className="slider-row"><span>{slots[0] ? dateLabel(slots[0].start, bucket) : '—'}</span><input aria-label="Время на карте" type="range" min={0} max={Math.max(slots.length - 1, 0)} value={safeIndex} disabled={slots.length < 2} onChange={(event) => setIndex(Number(event.target.value))} /><span>{slots.at(-1) ? dateLabel(slots.at(-1)!.start, bucket) : '—'}</span></div>
              </section>
            </main>
          </div>}
    </div>
  );
}
