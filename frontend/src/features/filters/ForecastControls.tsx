import {
  ActionIcon,
  Box,
  Button,
  Group,
  SegmentedControl,
  Select,
  Slider,
  Stack,
  Text,
  TextInput,
  Tooltip,
} from '@mantine/core';
import { IconPlayerPauseFilled, IconPlayerPlayFilled, IconPresentation } from '@tabler/icons-react';
import type { ForecastHorizon, ForecastMetric, ForecastPoint, RouteSummary } from '../../domain/types';

const HORIZON_DATA = [
  { label: 'День', value: 'day' },
  { label: 'Месяц', value: 'month' },
  { label: 'Год', value: 'year' },
];

function formatTimestamp(timestamp: string | undefined, horizon: ForecastHorizon) {
  if (!timestamp) return '—';
  const date = new Date(timestamp);
  if (horizon === 'year') return new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'long' }).format(date);
  return new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
  }).format(date);
}

interface ForecastControlsProps {
  horizon: ForecastHorizon;
  onHorizonChange: (value: ForecastHorizon) => void;
  metric: ForecastMetric;
  onMetricChange: (value: ForecastMetric) => void;
  routes: RouteSummary[];
  selectedRouteId: string | null;
  onRouteChange: (value: string | null) => void;
  points: ForecastPoint[];
  timeIndex: number;
  onTimeIndexChange: (value: number) => void;
  isPlaying: boolean;
  onPlayingChange: (value: boolean) => void;
  onDemo: () => void;
}

export function ForecastControls(props: ForecastControlsProps) {
  const current = props.points[props.timeIndex];
  const max = Math.max(0, props.points.length - 1);

  return (
    <Stack gap="lg">
      <Box>
        <Text className="control-label">Горизонт прогноза</Text>
        <SegmentedControl
          fullWidth
          value={props.horizon}
          onChange={(value) => props.onHorizonChange(value as ForecastHorizon)}
          data={HORIZON_DATA}
          className="horizon-control"
        />
      </Box>

      <Select
        label="Маршрут"
        searchable
        clearable
        nothingFoundMessage="Маршрут не найден"
        placeholder="Все маршруты"
        value={props.selectedRouteId}
        onChange={props.onRouteChange}
        data={props.routes.map((route) => ({
          value: route.routeId,
          label: `${route.routeRef} · ${route.routeName.replace(`${route.routeRef}: `, '')}`,
        }))}
      />

      <Box>
        <TextInput
          label="Дата"
          type="date"
          value={current?.timestamp.slice(0, 10) ?? ''}
          min={props.points[0]?.timestamp.slice(0, 10)}
          max={props.points[max]?.timestamp.slice(0, 10)}
          disabled={!props.points.length || props.horizon === 'day'}
          onChange={(event) => {
            const requestedDate = event.currentTarget.value;
            const currentHour = current ? new Date(current.timestamp).getHours() : 8;
            const candidates = props.points
              .map((point, index) => ({ point, index }))
              .filter(({ point }) => point.timestamp.startsWith(requestedDate));
            const closest = candidates.reduce((best, candidate) =>
              Math.abs(new Date(candidate.point.timestamp).getHours() - currentHour)
                < Math.abs(new Date(best.point.timestamp).getHours() - currentHour) ? candidate : best,
              candidates[0],
            );
            if (closest) props.onTimeIndexChange(closest.index);
          }}
          mb="lg"
        />
        <Group justify="space-between" mb={8}>
          <Text className="control-label" mb={0}>Момент времени</Text>
          <Text size="sm" fw={650} c="cyan.2">{formatTimestamp(current?.timestamp, props.horizon)}</Text>
        </Group>
        <Slider
          min={0}
          max={max}
          step={1}
          value={Math.min(props.timeIndex, max)}
          onChange={props.onTimeIndexChange}
          label={(value) => formatTimestamp(props.points[value]?.timestamp, props.horizon)}
          marks={max > 0 ? [{ value: 0 }, { value: Math.floor(max / 2) }, { value: max }] : []}
        />
        <Group justify="space-between" mt={16}>
          <Tooltip label={props.isPlaying ? 'Остановить анимацию' : 'Запустить анимацию'}>
            <ActionIcon
              size="lg"
              variant="light"
              color="cyan"
              onClick={() => props.onPlayingChange(!props.isPlaying)}
              aria-label={props.isPlaying ? 'Пауза' : 'Воспроизвести'}
            >
              {props.isPlaying ? <IconPlayerPauseFilled size={16} /> : <IconPlayerPlayFilled size={16} />}
            </ActionIcon>
          </Tooltip>
          <Text size="xs" c="dimmed">
            {props.horizon === 'day' ? 'Шаг 15 минут' : props.horizon === 'month' ? 'Шаг 1 час' : 'Шаг 1 день'}
          </Text>
        </Group>
        {props.horizon === 'day' && (
          <Group gap="xs" mt="sm" grow>
            <Button size="compact-xs" variant="subtle" onClick={() => props.onTimeIndexChange(33)}>Утро · 08:15</Button>
            <Button size="compact-xs" variant="subtle" onClick={() => props.onTimeIndexChange(72)}>Вечер · 18:00</Button>
          </Group>
        )}
      </Box>

      <Box>
        <Text className="control-label">Показатель</Text>
        <SegmentedControl
          fullWidth
          value={props.metric}
          onChange={(value) => props.onMetricChange(value as ForecastMetric)}
          data={[
            { value: 'load', label: 'Загрузка' },
            { value: 'boardings', label: 'Посадки' },
          ]}
        />
      </Box>

      <Button
        variant="gradient"
        gradient={{ from: 'cyan.7', to: 'teal.7' }}
        leftSection={<IconPresentation size={17} />}
        onClick={props.onDemo}
      >
        Демо: утренний пик
      </Button>
    </Stack>
  );
}
