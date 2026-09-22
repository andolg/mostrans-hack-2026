import type { StyleSpecification } from 'maplibre-gl';

export const mapConfig = {
  initialViewState: {
    longitude: 37.6176,
    latitude: 55.7558,
    zoom: 10.4,
  },
  minZoom: 8,
  maxZoom: 18,
  rasterTiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
  attribution: '© OpenStreetMap contributors',
};

export const baseMapStyle: StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: 'raster',
      tiles: mapConfig.rasterTiles,
      tileSize: 256,
      attribution: mapConfig.attribution,
    },
  },
  layers: [
    { id: 'osm', type: 'raster', source: 'osm', paint: { 'raster-saturation': -0.75, 'raster-brightness-max': 0.55, 'raster-contrast': 0.18 } },
  ],
};
