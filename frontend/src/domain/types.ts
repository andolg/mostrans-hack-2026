import type { FeatureCollection, LineString, Point } from 'geojson';

export type Bucket = 'hour' | 'day' | 'month';

export interface Metadata {
  routes: number[];
  historical_start: string;
  historical_end: string;
  precomputed_end: string;
  forecast_version: string;
}

export interface BoardingPoint {
  route: number;
  start: string;
  end: string;
  boardings: number;
  source: 'actual' | 'forecast';
}

export interface RouteProperties {
  routeId: string;
  routeRef: string;
  routeName: string;
  route?: number;
  color?: string;
  selected?: boolean;
}

export interface StopProperties {
  stopId: string;
  name: string;
}

export type RouteGeometry = FeatureCollection<LineString, RouteProperties>;
export type StopGeometry = FeatureCollection<Point, StopProperties>;
