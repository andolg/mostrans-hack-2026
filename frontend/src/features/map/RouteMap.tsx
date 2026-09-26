import { useMemo, useState } from 'react';
import MapView, { Layer, NavigationControl, Popup, Source, type MapLayerMouseEvent } from 'react-map-gl/maplibre';
import type { BoardingPoint, RouteGeometry, StopGeometry } from '../../domain/types';
import { baseMapStyle, mapConfig } from '../../config/map';

function routeColor(value: number, min: number, max: number) {
  const amount = max === min ? 0 : (value - min) / (max - min);
  const low = [139, 243, 166], middle = [255, 217, 112], high = [255, 149, 140];
  const from = amount < 0.5 ? low : middle;
  const to = amount < 0.5 ? middle : high;
  const fraction = (amount < 0.5 ? amount : amount - 0.5) * 2;
  return `rgb(${from.map((channel, index) => Math.round(channel + (to[index] - channel) * fraction)).join(',')})`;
}

interface Props {
  routes: RouteGeometry;
  stops: StopGeometry;
  supportedRoutes: number[];
  points: BoardingPoint[];
  snapshot: BoardingPoint[];
  selectedRoute: number | null;
  onSelectRoute: (route: number) => void;
}

export function RouteMap({ routes, stops, supportedRoutes, points, snapshot, selectedRoute, onSelectRoute }: Props) {
  const [hover, setHover] = useState<{ longitude: number; latitude: number; route: number } | null>(null);
  const coloredRoutes = useMemo(() => {
    const supported = new Set(supportedRoutes);
    const current = new Map(snapshot.map((point) => [point.route, point]));
    const ranges = new Map<number, { min: number; max: number }>();
    points.forEach((point) => {
      const range = ranges.get(point.route);
      ranges.set(point.route, { min: Math.min(range?.min ?? point.boardings, point.boardings), max: Math.max(range?.max ?? point.boardings, point.boardings) });
    });
    return {
      type: 'FeatureCollection' as const,
      features: routes.features.flatMap((feature) => {
        const route = Number(feature.properties.routeRef);
        if (!supported.has(route)) return [];
        const value = current.get(route)?.boardings;
        const range = ranges.get(route);
        return [{ ...feature, properties: { ...feature.properties, route, color: value !== undefined && range ? routeColor(value, range.min, range.max) : '#737373', selected: route === selectedRoute } }];
      }),
    };
  }, [routes, supportedRoutes, points, snapshot, selectedRoute]);

  const onPointer = (event: MapLayerMouseEvent) => {
    const route = Number(event.features?.[0]?.properties?.route);
    setHover(Number.isFinite(route) && route > 0 ? { longitude: event.lngLat.lng, latitude: event.lngLat.lat, route } : null);
  };
  const hoveredPoint = snapshot.find((point) => point.route === hover?.route);

  return <div className="map-wrap">
    <MapView initialViewState={mapConfig.initialViewState} minZoom={mapConfig.minZoom} maxZoom={mapConfig.maxZoom} mapStyle={baseMapStyle}
      attributionControl={{ compact: true }} interactiveLayerIds={['routes-hit']} onMouseMove={onPointer} onMouseLeave={() => setHover(null)}
      onClick={(event) => { const route = Number(event.features?.[0]?.properties?.route); if (route > 0) onSelectRoute(route); }} cursor={hover ? 'pointer' : 'grab'}>
      <NavigationControl position="top-right" showCompass={false} />
      <Source id="routes" type="geojson" data={coloredRoutes}>
        <Layer id="routes-base" type="line" paint={{ 'line-color': '#171717', 'line-width': 7, 'line-opacity': 0.85 }} layout={{ 'line-cap': 'round', 'line-join': 'round' }} />
        <Layer id="routes-color" type="line" filter={['==', ['get', 'selected'], false]} paint={{ 'line-color': ['get', 'color'], 'line-width': 4, 'line-opacity': 0.85 }} layout={{ 'line-cap': 'round', 'line-join': 'round' }} />
        <Layer id="route-selected" type="line" filter={['==', ['get', 'selected'], true]} paint={{ 'line-color': ['get', 'color'], 'line-width': 6, 'line-opacity': 1 }} layout={{ 'line-cap': 'round', 'line-join': 'round' }} />
        <Layer id="routes-hit" type="line" paint={{ 'line-color': '#ffffff', 'line-width': 16, 'line-opacity': 0 }} />
      </Source>
      <Source id="stops" type="geojson" data={stops}>
        <Layer id="stops-visual" type="circle" minzoom={11} paint={{ 'circle-radius': 2.5, 'circle-color': '#a6a6a6', 'circle-stroke-color': '#222222', 'circle-stroke-width': 1, 'circle-opacity': 0.85 }} />
      </Source>
      {hover && <Popup longitude={hover.longitude} latitude={hover.latitude} closeButton={false} closeOnClick={false} offset={12} className="route-popup">
        <strong>Маршрут {hover.route}</strong><br />{hoveredPoint ? `${new Intl.NumberFormat('ru-RU').format(hoveredPoint.boardings)} посадок · ${hoveredPoint.source === 'actual' ? 'факт' : 'прогноз'}` : 'Нет данных'}
      </Popup>}
    </MapView>
    <div className="map-legend"><span>Посадки на каждом маршруте</span><div><i className="legend-low" /> Минимум <i className="legend-high" /> Максимум</div></div>
  </div>;
}
