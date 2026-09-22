import { Badge, Box, Group, Text, ThemeIcon } from '@mantine/core';
import { IconRoute } from '@tabler/icons-react';

export function Brand() {
  return (
    <Group gap="sm" wrap="nowrap">
      <ThemeIcon size={36} radius={11} variant="gradient" gradient={{ from: 'cyan', to: 'teal' }}>
        <IconRoute size={21} stroke={2.2} />
      </ThemeIcon>
      <Box>
        <Group gap={8} wrap="nowrap">
          <Text fw={750} size="lg" lh={1}>МосТрам</Text>
          <Badge size="xs" variant="light" color="cyan">AI forecast</Badge>
        </Group>
        <Text size="xs" c="dimmed" mt={4}>Оперативный прогноз пассажиропотока</Text>
      </Box>
    </Group>
  );
}

