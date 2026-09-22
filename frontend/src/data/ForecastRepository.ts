import type {
  ForecastHorizon,
  NetworkSnapshot,
  OsmMetadata,
  RouteForecast,
  RouteGeometry,
  RouteSummary,
  StopForecast,
  StopGeometry,
} from '../domain/types';

export interface ForecastRepository {
  getRoutes(): Promise<RouteSummary[]>;
  getRouteGeometry(): Promise<RouteGeometry>;
  getStopGeometry(): Promise<StopGeometry>;
  getOsmMetadata(): Promise<OsmMetadata>;
  getRouteForecast(routeId: string, horizon: ForecastHorizon): Promise<RouteForecast>;
  getStopForecast(stopId: string, horizon: ForecastHorizon): Promise<StopForecast>;
  getNetworkSnapshot(timestamp: string, horizon: ForecastHorizon): Promise<NetworkSnapshot>;
}

