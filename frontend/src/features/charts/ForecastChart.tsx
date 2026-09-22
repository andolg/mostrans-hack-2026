import { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import { ActionIcon, Badge, Group, Paper, Skeleton, Text, Tooltip } from '@mantine/core';
import { IconArrowsMaximize, IconChartLine } from '@tabler/icons-react';
import type { ForecastHorizon, ForecastMetric, ForecastPoint } from '../../domain/types';

interface ForecastChartProps {
  points: ForecastPoint[];
  metric: ForecastMetric;
  horizon: ForecastHorizon;
  selectedIndex: number;
  title: string;
  loading?: boolean;
}

export function ForecastChart({ points, metric, horizon, selectedIndex, title, loading }: ForecastChartProps) {
  const option = useMemo(() => {
    const load = metric === 'load';
    const p50 = points.map((point) => load ? point.predictedLoad * 100 : point.predictedBoardings);
    const uncertaintyLow = points.map((point) => load ? (point.loadP10 ?? point.p10) * 100 : (point.boardingsP10 ?? point.p10));
    const uncertaintyBand = points.map((point) => load
      ? ((point.loadP90 ?? point.p90) - (point.loadP10 ?? point.p10)) * 100
      : (point.boardingsP90 ?? point.p90) - (point.boardingsP10 ?? point.p10));
    const labels = points.map((point) => formatAxis(point.timestamp, horizon));
    return {
      backgroundColor: 'transparent',
      animationDuration: 250,
      grid: { top: 18, right: 28, bottom: 28, left: 50 },
      tooltip: {
        trigger: 'axis',
        backgroundColor: '#111d2b',
        borderColor: '#32445a',
        textStyle: { color: '#edf5ff', fontSize: 12 },
        formatter: (params: Array<{ axisValue: string; value: number; seriesName: string }>) => {
          const median = params.find((item) => item.seriesName === 'P50');
          return `<b>${params[0]?.axisValue ?? ''}</b><br/>${load ? 'Оценочная загрузка' : 'Посадки'}: <b>${Math.round(median?.value ?? 0)}${load ? '%' : ''}</b>`;
        },
      },
      xAxis: {
        type: 'category', data: labels, boundaryGap: false,
        axisLabel: { color: '#8492a6', fontSize: 10, interval: Math.max(0, Math.floor(points.length / 8)) },
        axisLine: { lineStyle: { color: '#2b3b4f' } }, axisTick: { show: false },
      },
      yAxis: {
        type: 'value', min: 0, name: load ? '%' : 'пасс.', nameTextStyle: { color: '#728096' },
        axisLabel: { color: '#8492a6', fontSize: 10 }, splitLine: { lineStyle: { color: '#1d2c3e' } },
      },
      series: [
        { name: 'P10', type: 'line', stack: 'uncertainty', data: uncertaintyLow, symbol: 'none', lineStyle: { opacity: 0 }, areaStyle: { opacity: 0 } },
        { name: 'P10–P90', type: 'line', stack: 'uncertainty', data: uncertaintyBand, symbol: 'none', lineStyle: { opacity: 0 }, areaStyle: { color: 'rgba(34,211,238,.17)' }, silent: true },
        {
          name: 'P50', type: 'line', data: p50, symbol: 'none', smooth: 0.22,
          lineStyle: { color: '#22d3ee', width: 2.5 }, itemStyle: { color: '#22d3ee' },
          markLine: selectedIndex < points.length ? {
            symbol: 'none', silent: true, label: { show: false },
            lineStyle: { color: '#f8fafc', opacity: 0.55, type: 'dashed' },
            data: [{ xAxis: selectedIndex }],
          } : undefined,
        },
      ],
    };
  }, [points, metric, horizon, selectedIndex]);

  return (
    <Paper className="chart-panel" radius={0}>
      <Group justify="space-between" className="chart-header">
        <Group gap="sm">
          <IconChartLine size={18} color="#22d3ee" />
          <div>
            <Text size="sm" fw={700}>{title}</Text>
            <Text size="xs" c="dimmed">P50 и доверительный интервал P10–P90</Text>
          </div>
          <Badge size="xs" variant="outline" color="gray">Синтетический прогноз</Badge>
        </Group>
        <Tooltip label="График адаптируется к размеру панели">
          <ActionIcon variant="subtle" color="gray"><IconArrowsMaximize size={16} /></ActionIcon>
        </Tooltip>
      </Group>
      {loading ? <Skeleton height={150} m="md" /> : <ReactECharts option={option} style={{ height: 174, width: '100%' }} notMerge lazyUpdate />}
    </Paper>
  );
}

function formatAxis(timestamp: string, horizon: ForecastHorizon) {
  const date = new Date(timestamp);
  if (horizon === 'day') return new Intl.DateTimeFormat('ru-RU', { hour: '2-digit', minute: '2-digit' }).format(date);
  if (horizon === 'month') return new Intl.DateTimeFormat('ru-RU', { day: '2-digit', hour: '2-digit' }).format(date);
  return new Intl.DateTimeFormat('ru-RU', { day: '2-digit', month: 'short' }).format(date);
}
