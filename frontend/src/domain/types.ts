import type { FeatureCollection, LineString, Point } from 'geojson';

export type ForecastHorizon = 'day' | 'month' | 'year';
export type ForecastMetric = 'load' | 'boardings';

export interface RouteProperties {
  segmentId: string;
  routeId: string;
  routeName: string;
  routeRef: string;
  relationId: number;
  fromStopId: string;
  toStopId: string;
  sequence: number;
  predictedLoad?: number;
  predictedBoardings?: number;
  p10?: number;
  p90?: number;
  isSelected?: boolean;
}

export interface StopProperties {
  stopId: string;
  name: string;
  osmId: number;
  routeIds: string[];
  predictedLoad?: number;
  predictedBoardings?: number;
  p10?: number;
  p90?: number;
  isSelected?: boolean;
}

export type RouteGeometry = FeatureCollection<LineString, RouteProperties>;
export type StopGeometry = FeatureCollection<Point, StopProperties>;

export interface ForecastPoint {
  timestamp: string;
  predictedBoardings: number;
  predictedLoad: number;
  p10: number;
  p50: number;
  p90: number;
  loadP10?: number;
  loadP90?: number;
  boardingsP10?: number;
  boardingsP90?: number;
}

export interface RouteSummary {
  routeId: string;
  routeRef: string;
  routeName: string;
  relationId: number;
  segmentIds: string[];
}

export interface RouteForecast {
  routeId: string;
  horizon: ForecastHorizon;
  points: ForecastPoint[];
}

export interface StopForecast {
  stopId: string;
  horizon: ForecastHorizon;
  points: ForecastPoint[];
}

export interface SnapshotSegment {
  segmentId: string;
  routeId: string;
  predictedLoad: number;
  predictedBoardings: number;
  p10: number;
  p90: number;
}

export interface SnapshotStop {
  stopId: string;
  predictedLoad: number;
  predictedBoardings: number;
  p10: number;
  p90: number;
}

export interface NetworkSnapshot {
  timestamp: string;
  segments: SnapshotSegment[];
  stops: SnapshotStop[];
}

export interface ForecastFile {
  metadata: {
    generatedAt: string;
    seed: number;
    model: string;
    horizonDescriptions: Record<ForecastHorizon, string>;
  };
  routes?: Record<string, Record<ForecastHorizon, ForecastPoint[]>>;
  stops?: Record<string, Record<ForecastHorizon, ForecastPoint[]>>;
  segmentProfiles?: Record<string, { routeId: string; factor: number }>;
  stopProfiles?: Record<string, { routeIds: string[]; factor: number }>;
}

export interface OsmMetadata {
  generatedAt: string;
  source: string;
  routeCount: number;
  segmentCount: number;
  stopCount: number;
}
