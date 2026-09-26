import type { BoardingPoint, Bucket, Metadata, RouteGeometry, StopGeometry } from '../domain/types';

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    const detail = await response.json().then((body) => body.detail).catch(() => undefined);
    throw new Error(typeof detail === 'string' ? detail : `HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const getMetadata = () => getJson<Metadata>('/api/metadata');

export async function getBoardings(from: string, to: string, bucket: Bucket): Promise<BoardingPoint[]> {
  const params = new URLSearchParams({ from: `${from}T00:00`, to: `${to}T00:00`, group_by: bucket });
  const result = await getJson<{ points: BoardingPoint[] }>(`/api/boardings?${params}`);
  return result.points;
}

export const getRoutes = () => getJson<RouteGeometry>('/data/osm/tram_routes.geojson');
export const getStops = () => getJson<StopGeometry>('/data/osm/tram_stops.geojson');

export function exportUrl(from: string, to: string, bucket: Bucket, route?: number): string {
  const params = new URLSearchParams({ from: `${from}T00:00`, to: `${to}T00:00`, group_by: bucket });
  if (route !== undefined) params.set('route', String(route));
  return `/api/boardings/export?${params}`;
}
