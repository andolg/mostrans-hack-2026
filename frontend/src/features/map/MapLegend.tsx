import { Paper, Stack, Text } from '@mantine/core';

const bands = [
  { color: '#2dd4bf', label: '0–30%', caption: 'Свободно' },
  { color: '#84cc16', label: '30–60%', caption: 'Умеренно' },
  { color: '#facc15', label: '60–80%', caption: 'Плотно' },
  { color: '#fb923c', label: '80–100%', caption: 'Очень плотно' },
  { color: '#ef4444', label: '100%+', caption: 'Перегрузка' },
];

export function MapLegend() {
  return (
    <Paper className="map-legend" p="sm" radius="md">
      <Text fw={700} size="sm">Оценочная загрузка</Text>
      <Text c="dimmed" size="xs" mb={8}>от номинальной вместимости</Text>
      <Stack gap={5}>
        {bands.map((band) => (
          <div className="legend-row" key={band.label}>
            <span className="legend-swatch" style={{ background: band.color }} />
            <Text size="xs" fw={650}>{band.label}</Text>
            <Text size="xs" c="dimmed">{band.caption}</Text>
          </div>
        ))}
      </Stack>
    </Paper>
  );
}

