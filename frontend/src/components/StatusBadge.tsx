import { Badge } from '@mantine/core';
import { IconCircleCheckFilled } from '@tabler/icons-react';

export function StatusBadge({ generatedAt }: { generatedAt?: string }) {
  const label = generatedAt
    ? `Прогноз обновлён ${new Intl.DateTimeFormat('ru-RU', { day: '2-digit', month: 'short' }).format(new Date(generatedAt))}`
    : 'Данные загружены';
  return <Badge color="teal" variant="light" leftSection={<IconCircleCheckFilled size={11} />}>{label}</Badge>;
}

