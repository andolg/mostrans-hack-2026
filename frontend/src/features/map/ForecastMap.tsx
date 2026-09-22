import { useMemo, useState } from 'react';
import MapView, { Layer, NavigationControl, Popup, Source, type MapLayerMouseEvent } from 'react-map-gl/maplibre';
import type { FeatureCollection, LineString, Point } from 'geojson';
import type { ExpressionSpecification } from 'maplibre-gl';
import { Badge, Group, Text } from '@mantine/core';
import { baseMapStyle, mapConfig } from '../../config/map';
import type {
  ForecastMetric,
  NetworkSnapshot,
  RouteGeometry,
  StopGeometry,
} from '../../domain/types';
import { MapLegend } from './MapLegend';

const LOAD_COLOR: ExpressionSpecification = [
  'interpolate', ['linear'], ['coalesce', ['get', 'predictedLoad'], 0],
  0, '#2dd4bf', 0.3, '#84cc16', 0.6, '#facc15', 0.8, '#fb923c', 1, '#ef4444', 1.4, '#be123c',
];

interface HoverInfo {
  longitude: number;
  latitude: number;
  kind: 'route' | 'stop';
  properties: Record<string, unknown>;
}

interface ForecastMapProps {
  routes: RouteGeometry;
  stops: StopGeometry;
  snapshot?: NetworkSnapshot;
  metric: ForecastMetric;
  selectedRouteId: string | null;
  selectedStopId: string | null;
  timestamp?: string;
  onSelectRoute: (routeId: string) => void;
  onSelectStop: (stopId: string) => void;
}

export function ForecastMap({
  routes, stops, snapshot, metric, selectedRouteId, selectedStopId, timestamp, onSelectRoute, onSelectStop,
}: ForecastMapProps) {
  const [hover, setHover] = useState<HoverInfo | null>(null);
  const segmentData = useMemo(() => {
    const values = new Map(snapshot?.segments.map((segment) => [segment.segmentId, segment]));
    return {
      ...routes,
      features: routes.features.map((feature) => {
        const forecast = values.get(feature.properties.segmentId);
        return {
          ...feature,
          properties: {
            ...feature.properties,
            ...forecast,
            isSelected: selectedRouteId === null || feature.properties.routeId === selectedRouteId,
          },
        };
      }),
    } as FeatureCollection<LineString>;
  }, [routes, snapshot, selectedRouteId]);

  const stopData = useMemo(() => {
    const values = new Map(snapshot?.stops.map((stop) => [stop.stopId, stop]));
    return {
      ...stops,
      features: stops.features.map((feature) => ({
        ...feature,
        properties: {
          ...feature.properties,
          ...values.get(feature.properties.stopId),
          isSelected: feature.properties.stopId === selectedStopId,
        },
      })),
    } as FeatureCollection<Point>;
  }, [stops, snapshot, selectedStopId]);

  const onPointer = (event: MapLayerMouseEvent) => {
    const feature = event.features?.[0];
    if (!feature) return setHover(null);
    setHover({
      longitude: event.lngLat.lng,
      latitude: event.lngLat.lat,
      kind: feature.layer.id === 'tram-stops' ? 'stop' : 'route',
      properties: feature.properties ?? {},
    });
  };

  const onClick = (event: MapLayerMouseEvent) => {
    const feature = event.features?.[0];
    if (!feature?.properties) return;
    if (feature.layer.id === 'tram-stops') onSelectStop(String(feature.properties.stopId));
    else onSelectRoute(String(feature.properties.routeId));
  };

  const p = hover?.properties;
  const load = Number(p?.predictedLoad ?? 0);
  const boardings = Number(p?.predictedBoardings ?? 0);

  return (
    <div className="map-wrap">
      <MapView
        initialViewState={mapConfig.initialViewState}
        minZoom={mapConfig.minZoom}
        maxZoom={mapConfig.maxZoom}
        mapStyle={baseMapStyle}
        interactiveLayerIds={['tram-stops', 'tram-routes-hit']}
        onMouseMove={onPointer}
        onMouseLeave={() => setHover(null)}
        onClick={onClick}
        cursor={hover ? 'pointer' : 'grab'}
        attributionControl={{ compact: true }}
      >
        <NavigationControl position="top-right" showCompass={false} />
        <Source id="tram-routes" type="geojson" data={segmentData}>
          <Layer
            id="tram-routes-shadow"
            type="line"
            paint={{ 'line-color': '#020617', 'line-width': 8, 'line-opacity': 0.45, 'line-blur': 2 }}
          />
          <Layer
            id="tram-routes-load"
            type="line"
            paint={{
              'line-color': LOAD_COLOR,
              'line-width': ['case', ['>', ['get', 'predictedLoad'], 1], 6, 4],
              'line-opacity': ['case', ['get', 'isSelected'], 0.95, 0.15],
            }}
            layout={{ 'line-cap': 'round', 'line-join': 'round' }}
          />
          <Layer id="tram-routes-hit" type="line" paint={{ 'line-color': '#ffffff', 'line-width': 14, 'line-opacity': 0 }} />
        </Source>
        <Source id="tram-stops-source" type="geojson" data={stopData}>
          <Layer
            id="tram-stops"
            type="circle"
            minzoom={10}
            paint={{
              'circle-radius': metric === 'boardings'
                ? ['interpolate', ['linear'], ['coalesce', ['get', 'predictedBoardings'], 0], 0, 3, 80, 6, 250, 10]
                : ['interpolate', ['linear'], ['coalesce', ['get', 'predictedLoad'], 0], 0, 3, 1, 7, 1.4, 10],
              'circle-color': LOAD_COLOR,
              'circle-stroke-color': ['case', ['get', 'isSelected'], '#ffffff', '#07111e'],
              'circle-stroke-width': ['case', ['get', 'isSelected'], 3, 1.5],
              'circle-opacity': ['interpolate', ['linear'], ['zoom'], 10, 0.65, 12, 0.95],
            }}
          />
        </Source>

        {hover && p && (
          <Popup
            longitude={hover.longitude}
            latitude={hover.latitude}
            closeButton={false}
            closeOnClick={false}
            offset={12}
            className="forecast-popup"
          >
            <Text fw={750} size="sm">
              {hover.kind === 'stop' ? String(p.name ?? 'Остановка') : `Маршрут ${String(p.routeRef ?? '')}`}
            </Text>
            {hover.kind === 'stop' && <Text size="xs" c="dimmed">Маршруты: {parseRouteIds(p.routeIds)}</Text>}
            <Group gap={6} mt={7}>
              <Badge color={load > 1 ? 'red' : load > 0.8 ? 'orange' : 'teal'} size="sm">
                {Math.round(load * 100)}%
              </Badge>
              <Text size="xs">{boardings} посадок</Text>
            </Group>
            <Text size="xs" c="dimmed" mt={5}>
              {timestamp ? formatTime(timestamp) : ''} · P10–P90: {hover.kind === 'stop'
                ? `${Math.round(boardings * 0.88)}–${Math.round(boardings * 1.12)} пасс.`
                : `${Math.round(Number(p.p10 ?? 0) * 100)}–${Math.round(Number(p.p90 ?? 0) * 100)}%`}
            </Text>
          </Popup>
        )}
      </MapView>
      <MapLegend />
    </div>
  );
}

function parseRouteIds(value: unknown) {
  if (Array.isArray(value)) return value.join(', ');
  if (typeof value !== 'string') return '—';
  try { return (JSON.parse(value) as string[]).join(', '); } catch { return value; }
}

function formatTime(timestamp: string) {
  return new Intl.DateTimeFormat('ru-RU', { hour: '2-digit', minute: '2-digit' }).format(new Date(timestamp));
}
