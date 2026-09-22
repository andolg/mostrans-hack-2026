import type { ForecastRepository } from './ForecastRepository';
import type {
  ForecastFile,
  ForecastHorizon,
  ForecastPoint,
  NetworkSnapshot,
  OsmMetadata,
  RouteForecast,
  RouteGeometry,
  RouteSummary,
  StopForecast,
  StopGeometry,
} from '../domain/types';

const DATA_ROOT = import.meta.env.VITE_DATA_ROOT ?? '/data';

async function loadJson<T>(path: string): Promise<T> {
  const response = await fetch(`${DATA_ROOT}/${path}`);
  if (!response.ok) throw new Error(`Не удалось загрузить ${path} (${response.status})`);
  return response.json() as Promise<T>;
}

function nearest(points: ForecastPoint[], timestamp: string): ForecastPoint {
  if (!points.length) throw new Error('Прогноз не содержит точек');
  const target = Date.parse(timestamp);
  return points.reduce((best, point) =>
    Math.abs(Date.parse(point.timestamp) - target) < Math.abs(Date.parse(best.timestamp) - target) ? point : best,
  );
}

const HORIZON_UNCERTAINTY: Record<ForecastHorizon, number> = { day: 0.12, month: 0.19, year: 0.29 };

function deriveStopPoints(
  routeData: ForecastFile,
  routeIds: string[],
  factor: number,
  horizon: ForecastHorizon,
): ForecastPoint[] {
  const series = routeIds.flatMap((routeId) => {
    const points = routeData.routes?.[routeId]?.[horizon];
    return points ? [points] : [];
  });
  if (!series.length) return [];
  const uncertainty = HORIZON_UNCERTAINTY[horizon];
  return series[0].map((point, index) => {
    const boardings = Math.round(series.reduce((sum, values) => sum + values[index].predictedBoardings, 0) / series.length * factor);
    const load = Math.min(1.45, series.reduce((sum, values) => sum + values[index].predictedLoad, 0) / series.length * (0.82 + factor * 0.18));
    return {
      timestamp: point.timestamp,
      predictedBoardings: boardings,
      predictedLoad: load,
      p10: Math.round(boardings * (1 - uncertainty)),
      p50: boardings,
      p90: Math.round(boardings * (1 + uncertainty)),
      loadP10: Math.max(0, load * (1 - uncertainty)),
      loadP90: Math.min(1.5, load * (1 + uncertainty)),
      boardingsP10: Math.round(boardings * (1 - uncertainty)),
      boardingsP90: Math.round(boardings * (1 + uncertainty)),
    };
  });
}

export class StaticForecastRepository implements ForecastRepository {
  private routeGeometry?: Promise<RouteGeometry>;
  private stopGeometry?: Promise<StopGeometry>;
  private routeData?: Promise<ForecastFile>;
  private stopData?: Promise<ForecastFile>;

  getRouteGeometry() {
    return (this.routeGeometry ??= loadJson<RouteGeometry>('osm/tram_routes.geojson'));
  }

  getStopGeometry() {
    return (this.stopGeometry ??= loadJson<StopGeometry>('osm/tram_stops.geojson'));
  }

  getOsmMetadata() {
    return loadJson<OsmMetadata>('osm/metadata.json');
  }

  private getRouteData() {
    return (this.routeData ??= loadJson<ForecastFile>('mock/route_forecasts.json'));
  }

  private getStopData() {
    return (this.stopData ??= loadJson<ForecastFile>('mock/stop_forecasts.json'));
  }

  async getRoutes(): Promise<RouteSummary[]> {
    const geometry = await this.getRouteGeometry();
    const routes = new Map<string, RouteSummary>();
    geometry.features.forEach(({ properties }) => {
      const route = routes.get(properties.routeId) ?? {
        routeId: properties.routeId,
        routeRef: properties.routeRef,
        routeName: properties.routeName,
        relationId: properties.relationId,
        segmentIds: [],
      };
      route.segmentIds.push(properties.segmentId);
      routes.set(properties.routeId, route);
    });
    return [...routes.values()].sort((a, b) =>
      a.routeRef.localeCompare(b.routeRef, 'ru', { numeric: true }),
    );
  }

  async getRouteForecast(routeId: string, horizon: ForecastHorizon): Promise<RouteForecast> {
    const data = await this.getRouteData();
    const points = data.routes?.[routeId]?.[horizon];
    if (!points) throw new Error(`Нет прогноза для маршрута ${routeId}`);
    return { routeId, horizon, points };
  }

  async getStopForecast(stopId: string, horizon: ForecastHorizon): Promise<StopForecast> {
    const [data, routes] = await Promise.all([this.getStopData(), this.getRouteData()]);
    const profile = data.stopProfiles?.[stopId];
    const points = profile && deriveStopPoints(routes, profile.routeIds, profile.factor, horizon);
    if (!points?.length) throw new Error(`Нет прогноза для остановки ${stopId}`);
    return { stopId, horizon, points };
  }

  async getNetworkSnapshot(timestamp: string, horizon: ForecastHorizon): Promise<NetworkSnapshot> {
    const [routes, stops] = await Promise.all([this.getRouteData(), this.getStopData()]);
    const routePoint = new Map<string, ForecastPoint>();
    Object.entries(routes.routes ?? {}).forEach(([routeId, horizons]) => {
      routePoint.set(routeId, nearest(horizons[horizon], timestamp));
    });

    const segments = Object.entries(routes.segmentProfiles ?? {}).flatMap(([segmentId, profile]) => {
      const point = routePoint.get(profile.routeId);
      if (!point) return [];
      const load = Math.min(1.45, point.predictedLoad * profile.factor);
      return [{
        segmentId,
        routeId: profile.routeId,
        predictedLoad: load,
        predictedBoardings: Math.round(point.predictedBoardings * profile.factor),
        p10: Math.min(1.45, point.p10 * profile.factor),
        p90: Math.min(1.45, point.p90 * profile.factor),
      }];
    });

    const snapshotStops = Object.entries(stops.stopProfiles ?? {}).flatMap(([stopId, profile]) => {
      const routePoints = profile.routeIds.flatMap((routeId) => {
        const point = routePoint.get(routeId);
        return point ? [point] : [];
      });
      if (!routePoints.length) return [];
      const boardings = Math.round(routePoints.reduce((sum, point) => sum + point.predictedBoardings, 0) / routePoints.length * profile.factor);
      const load = Math.min(1.45, routePoints.reduce((sum, point) => sum + point.predictedLoad, 0) / routePoints.length * (0.82 + profile.factor * 0.18));
      const uncertainty = HORIZON_UNCERTAINTY[horizon];
      return {
        stopId,
        predictedLoad: load,
        predictedBoardings: boardings,
        p10: Math.max(0, load * (1 - uncertainty)),
        p90: Math.min(1.5, load * (1 + uncertainty)),
      };
    });
    return { timestamp, segments, stops: snapshotStops };
  }
}
