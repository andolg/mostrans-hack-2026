# Tram Passenger Forecast Frontend — Implementation Specification

## 1. Purpose

This document is an implementation brief for building the first runnable version of a tram passenger-flow forecasting web application for a hackathon project.

The immediate goal is to build a **self-contained frontend service** that:

- runs as a Docker container;
- serves a polished interactive web application;
- displays Moscow tram routes and stops on an interactive map;
- visualizes plausible passenger-load forecasts;
- supports forecast horizons of:
  - 1 day;
  - 1 month;
  - 1 year;
- allows filtering by route, stop, date/time, and forecast horizon;
- currently uses locally generated mock prediction data instead of a backend API;
- is structured so that mock data can later be replaced by requests to a real backend without redesigning the frontend.

The mock forecast generator and OpenStreetMap import scripts are **development/offline utilities**. They are not part of the runtime application and should remain reusable for future data refreshes.

---

# 2. Long-Term System Architecture

The target architecture should separate frontend visualization, backend/API logic, ML prediction generation, and persistent data.

```text
                         Browser
                            |
                            v
                 +----------------------+
                 | Frontend container   |
                 | React SPA + nginx    |
                 +----------+-----------+
                            |
                       /api/* later
                            |
                            v
                 +----------------------+
                 | Backend API          |
                 | Java 17+             |
                 | Spring Boot          |
                 +----------+-----------+
                            |
                   +--------+--------+
                   |                 |
                   v                 v
          +----------------+   +----------------+
          | PostgreSQL /   |   | Optional cache |
          | PostGIS        |   | Redis          |
          +----------------+   +----------------+
                   ^
                   |
          predictions / aggregates
                   |
          +----------------------+
          | ML / data pipeline   |
          | Python               |
          | offline or worker    |
          +----------------------+
```

For the current stage, only the frontend container is required.

The browser should read:

```text
/public/data/osm/*
/public/data/mock/*
```

instead of calling a backend.

The code must introduce a small data-access abstraction so that the data source can later change from:

```text
Static JSON / GeoJSON
```

to:

```text
REST API
```

without changing the UI components.

---

# 3. Current Development Architecture

For the first implementation:

```text
offline scripts
     |
     +--> fetch OSM tram geometry
     |        |
     |        v
     |   GeoJSON files
     |
     +--> generate mock predictions
              |
              v
         JSON files
              |
              v

+-------------------------------------------+
| frontend Docker container                 |
|                                           |
| React + TypeScript + Vite                 |
| built to static assets                    |
| served by nginx                           |
|                                           |
| /data/osm/*.geojson                       |
| /data/mock/*.json                         |
+-------------------------------------------+
```

No backend is required yet.

Do **not** put OSM downloading or mock-data generation in the Docker container startup path.

The Docker image should contain already-generated static files.

---

# 4. Repository Layout

Use a structure similar to:

```text
tram-forecast/
|
|-- frontend/
|   |-- src/
|   |   |-- app/
|   |   |-- components/
|   |   |-- features/
|   |   |   |-- map/
|   |   |   |-- forecast/
|   |   |   |-- filters/
|   |   |   |-- charts/
|   |   |
|   |   |-- data/
|   |   |   |-- ForecastRepository.ts
|   |   |   |-- StaticForecastRepository.ts
|   |   |   |-- ApiForecastRepository.ts
|   |   |
|   |   |-- domain/
|   |   |   |-- types.ts
|   |   |
|   |   |-- hooks/
|   |   |-- utils/
|   |   |-- main.tsx
|   |   `-- App.tsx
|   |
|   |-- public/
|   |   `-- data/
|   |       |-- osm/
|   |       |   |-- tram_routes.geojson
|   |       |   |-- tram_stops.geojson
|   |       |   `-- metadata.json
|   |       |
|   |       `-- mock/
|   |           |-- route_forecasts.json
|   |           |-- stop_forecasts.json
|   |           `-- metadata.json
|   |
|   |-- Dockerfile
|   |-- nginx.conf
|   |-- package.json
|   `-- vite.config.ts
|
|-- tools/
|   |-- osm/
|   |   |-- fetch_osm_trams.py
|   |   |-- normalize_osm.py
|   |   `-- README.md
|   |
|   `-- mock-data/
|       |-- generate_forecasts.py
|       `-- README.md
|
|-- docker-compose.yml
|-- README.md
`-- docs/
    `-- architecture.md
```

The exact folder names may differ slightly, but keep clear separation between:

- runtime frontend;
- static application data;
- offline utilities;
- future backend/ML architecture documentation.

---

# 5. Frontend Technology Stack

Use:

- **TypeScript**
- **React**
- **Vite**
- **MapLibre GL JS**
- **react-map-gl/maplibre**
- **Mantine**
- **Apache ECharts**
- **TanStack Query**

Optional:

- `date-fns` for date handling;
- `zod` for runtime validation of loaded static JSON;
- `zustand` only if global UI state becomes complex.

Avoid adding Redux unless a real need appears.

Avoid Next.js. This application is a client-side analytical dashboard and does not need SSR or SEO.

---

# 6. Map Design

## 6.1 Base map

Use MapLibre.

The basemap source must be configurable in one place.

For development, an OpenStreetMap raster tile source may be used.

Do not hard-code map provider logic throughout the application.

Example conceptual config:

```ts
export const mapConfig = {
  rasterTiles: [
    "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
  ],
  attribution: "© OpenStreetMap contributors"
};
```

The application must visibly show the OpenStreetMap attribution.

The application should not attempt to preload, scrape, or bulk-download map tiles.

---

## 6.2 Initial viewport

Center the application approximately on Moscow.

Suggested initial values:

```text
longitude: 37.6176
latitude: 55.7558
zoom: 10.5
```

Make these values configurable.

---

## 6.3 Application layers

Render application data as layers above the basemap.

Recommended layers:

```text
1. basemap
2. optional subtle tram-network background
3. route load segments
4. tram stops
5. selected route highlight
6. selected stop highlight
7. hover state
8. popups/tooltips
```

---

# 7. OSM Tram Data

## 7.1 OSM import should be offline

OSM tram data should be retrieved using an offline utility.

Do not query Overpass from the browser during normal application operation.

The workflow should be:

```text
Overpass / OSM
      |
      v
tools/osm/fetch_osm_trams.py
      |
      v
raw OSM response
      |
      v
tools/osm/normalize_osm.py
      |
      +--> tram_routes.geojson
      +--> tram_stops.geojson
      `--> metadata.json
```

---

## 7.2 Relevant OSM concepts

The extraction logic should consider common tram-related tags including:

```text
railway=tram
railway=tram_stop
route=tram
public_transport=stop_position
public_transport=platform
tram=yes
```

Prefer extracting route relations when possible, because they contain useful route membership and stop ordering information.

However, the importer should be defensive because OSM tagging may not be perfectly uniform.

---

## 7.3 Required output

### `tram_stops.geojson`

Use a `FeatureCollection`.

Each feature should preferably contain:

```json
{
  "type": "Feature",
  "geometry": {
    "type": "Point",
    "coordinates": [37.61, 55.75]
  },
  "properties": {
    "stopId": "osm:123456",
    "name": "Example stop",
    "osmId": 123456,
    "routeIds": ["17", "38"]
  }
}
```

### `tram_routes.geojson`

Represent the network as line features.

For visualization, it is useful to normalize routes into line segments between consecutive stops.

Each feature should preferably contain:

```json
{
  "type": "Feature",
  "geometry": {
    "type": "LineString",
    "coordinates": [
      [37.61, 55.75],
      [37.62, 55.76]
    ]
  },
  "properties": {
    "segmentId": "17:stopA:stopB",
    "routeId": "17",
    "routeName": "17",
    "fromStopId": "stopA",
    "toStopId": "stopB",
    "sequence": 12
  }
}
```

If exact stop-to-stop route segmentation is too complex for the first version, begin with route LineStrings and add segmentation later.

However, the final visualization should preferably be segment-based because predicted vehicle load is naturally associated with route segments rather than the full route.

---

# 8. Mock Forecast Data

The initial application must use deterministic but plausible synthetic passenger forecasts.

The generator should be located in:

```text
tools/mock-data/generate_forecasts.py
```

Use Python.

Recommended libraries:

```text
numpy
pandas
```

Polars may be used instead of pandas if desired.

The generator must accept a random seed.

For example:

```bash
python tools/mock-data/generate_forecasts.py --seed 42
```

Running the same seed should reproduce the same output.

---

# 9. Synthetic Demand Model

The mock data should look realistic enough to demonstrate the application.

Do not use completely independent random values.

Use a structured model.

For each route `r`, assign persistent route-specific parameters.

Example:

```text
baseDemand_r
morningPeakAmplitude_r
eveningPeakAmplitude_r
morningPeakTime_r
eveningPeakTime_r
morningPeakWidth_r
eveningPeakWidth_r
weekendFactor_r
routeCapacity_r
routeNoiseScale_r
```

Use Gaussian-shaped rush-hour demand.

For time `t` in hours:

```text
G(t; mu, sigma) =
    exp(-(t - mu)^2 / (2 * sigma^2))
```

A route-level demand curve can be:

```text
demand_r(t) =
    baseDemand_r
    + morningPeakAmplitude_r * G(t; morningPeakTime_r, morningPeakWidth_r)
    + eveningPeakAmplitude_r * G(t; eveningPeakTime_r, eveningPeakWidth_r)
```

Example parameters:

```text
morning peak:
    center between 07:15 and 09:15
    sigma between 0.6 and 1.3 hours

evening peak:
    center between 16:30 and 19:30
    sigma between 0.8 and 1.6 hours
```

Different routes should have different deterministic parameters derived from the random seed and route ID.

---

# 10. Additional Realism for Mock Data

Add several modifiers.

## 10.1 Day-of-week effect

Example:

```text
Mon-Thu: 1.00
Friday: 0.95 to 1.05
Saturday: 0.70 to 0.85
Sunday: 0.60 to 0.80
```

Use route-specific variation.

---

## 10.2 Seasonal effect

For long-range forecasts, use a smooth annual seasonal component.

Example:

```text
season(t) =
    1 + A * cos(2*pi*(dayOfYear - phase)/365)
```

Keep amplitude modest, for example:

```text
A = 0.05 to 0.15
```

---

## 10.3 Stop effect

Stops should have stable relative attractiveness.

For each stop:

```text
stopWeight_s = random value around 1.0
```

Major synthetic stops may have weights around:

```text
1.5 to 2.5
```

Minor stops may have:

```text
0.4 to 0.8
```

The generator should ideally infer some plausible stop importance from graph characteristics:

- number of routes serving the stop;
- centrality proxy;
- stop sequence position.

If this is too much effort, seeded random weights are acceptable.

---

## 10.4 Directional / segment effect

Vehicle load should vary along a route.

A simple approximation:

```text
segmentLoad =
    routeDemand
    * routeSegmentProfile
```

Generate a smooth segment profile rather than independent random values.

For example:

- lower values near route terminals;
- increasing values toward central portions;
- decreasing toward the opposite terminal.

A simple normalized profile can be based on:

```text
sin(pi * normalizedRoutePosition)
```

with route-specific skew.

Example:

```text
segmentFactor(x) =
    0.4
    + 0.9 * sin(pi * x)^p
```

where:

```text
x in [0, 1]
p is route-specific
```

Add small correlated noise.

---

## 10.5 Noise

Use small random noise, not dominant noise.

For example:

```text
observedLikePrediction =
    structuredDemand
    * (1 + Normal(0, 0.03 ... 0.08))
```

Clamp negative values to zero.

---

# 11. Forecast Horizons

The interface must expose:

```text
Day
Month
Year
```

These represent different planning horizons.

The mock-data generator should provide different resolutions.

Recommended:

## Day horizon

Resolution:

```text
15 minutes
```

Range:

```text
24 hours
```

Use the most detailed peak structure.

---

## Month horizon

Resolution:

```text
1 hour
```

or:

```text
daily aggregates + typical intraday profile
```

For UI simplicity, hourly samples for selected dates are acceptable.

The mock data should show weekday/weekend differences.

---

## Year horizon

Resolution:

```text
1 day
```

The yearly horizon should emphasize:

- annual seasonality;
- weekday/weekend effects;
- slow trend;
- uncertainty.

Do not generate 15-minute values for an entire year unless needed.

---

# 12. Prediction Uncertainty

The generated data should include uncertainty bands.

For every prediction provide approximately:

```text
p10
p50
p90
```

Example:

```text
p50 = forecast
uncertainty = horizon-dependent

Day:
    ±8-15%

Month:
    ±12-22%

Year:
    ±18-35%
```

These do not need to be statistically perfect. They exist to demonstrate that longer-term forecasts are less certain.

Ensure:

```text
p10 <= p50 <= p90
```

---

# 13. Suggested Forecast Data Schema

A compact structure is preferred over huge duplicated JSON.

For the first implementation, optimize for simplicity.

Example:

```json
{
  "metadata": {
    "generatedAt": "2026-09-22T00:00:00Z",
    "seed": 42,
    "model": "synthetic-gaussian-v1"
  },
  "routes": {
    "17": {
      "day": [
        {
          "timestamp": "2026-09-23T07:00:00",
          "predictedBoardings": 220,
          "predictedLoad": 0.61,
          "p10": 190,
          "p50": 220,
          "p90": 255
        }
      ]
    }
  }
}
```

For segment visualization, a second dataset may be cleaner:

```json
{
  "segments": {
    "17:stopA:stopB": {
      "day": [
        {
          "timestamp": "2026-09-23T07:00:00",
          "load": 0.74
        }
      ]
    }
  }
}
```

Do not prematurely optimize file size unless it becomes a problem.

---

# 14. Domain Model

Create shared TypeScript domain types.

Example:

```ts
type ForecastHorizon = "day" | "month" | "year";

interface TramStop {
  stopId: string;
  name: string;
  routeIds: string[];
  longitude: number;
  latitude: number;
}

interface TramSegment {
  segmentId: string;
  routeId: string;
  fromStopId: string;
  toStopId: string;
  sequence: number;
}

interface ForecastPoint {
  timestamp: string;
  predictedBoardings: number;
  predictedLoad: number;
  p10?: number;
  p50?: number;
  p90?: number;
}
```

Use normalized IDs everywhere.

---

# 15. Data Access Abstraction

Do not let React components directly fetch static JSON files.

Create an interface.

Example:

```ts
export interface ForecastRepository {
  getRoutes(): Promise<RouteSummary[]>;

  getRouteForecast(
    routeId: string,
    horizon: ForecastHorizon
  ): Promise<RouteForecast>;

  getStopForecast(
    stopId: string,
    horizon: ForecastHorizon
  ): Promise<StopForecast>;

  getNetworkSnapshot(
    timestamp: string,
    horizon: ForecastHorizon
  ): Promise<NetworkSnapshot>;
}
```

Current implementation:

```text
StaticForecastRepository
```

Future implementation:

```text
ApiForecastRepository
```

The application should switch repository implementation via configuration.

This is important because the real backend is not available yet.

---

# 16. Future Backend API Shape

Design the frontend so it can later call endpoints similar to:

```http
GET /api/routes
GET /api/routes/{routeId}
GET /api/stops/{stopId}

GET /api/forecast/network
    ?horizon=day
    &timestamp=2026-09-23T08:00:00

GET /api/forecast/routes/{routeId}
    ?horizon=day
    &from=...
    &to=...

GET /api/forecast/stops/{stopId}
    ?horizon=day
    &from=...
    &to=...
```

Do not implement these endpoints yet.

---

# 17. Main UI Layout

The application should look like an operational transport dashboard rather than a traditional website.

Use almost the entire viewport for the map.

Recommended layout:

```text
+--------------------------------------------------------------+
| Tram Flow Forecast      [Day] [Month] [Year]         status |
+----------------+---------------------------------------------+
|                |                                             |
| Route          |                                             |
| [All       v]  |                                             |
|                |                                             |
| Date           |                  MAP                        |
| [2026-09-23]   |                                             |
|                |                                             |
| Time           |                                             |
| [07:30]        |                                             |
|                |                                             |
| Metric         |                                  Legend     |
| Load           |                                             |
| Boardings      |                                             |
|                |                                             |
+----------------+---------------------------------------------+
|                 selected object forecast chart              |
+--------------------------------------------------------------+
```

Prefer responsive overlay panels rather than a large permanent desktop sidebar when screen space is limited.

---

# 18. Visual Style

The interface should be clean, modern, and professional.

Use Mantine as the component library.

Avoid excessive decoration.

Design direction:

```text
transport operations dashboard
data-heavy but uncluttered
dark map-compatible controls
clear hierarchy
large map area
few strong accent colors
```

Use:

- rounded but restrained panels;
- subtle shadows;
- translucent or slightly opaque map overlays;
- clear typography;
- compact controls;
- responsive resizing.

A dark theme is acceptable and may suit a map-heavy dashboard well.

A light theme is also acceptable.

Implement one polished theme first instead of spending time on theme switching.

---

# 19. Forecast Horizon Control

Place a prominent segmented control near the top:

```text
[ Day ] [ Month ] [ Year ]
```

Changing horizon must update:

- chart resolution;
- available time controls;
- forecast uncertainty;
- map snapshot data.

---

# 20. Time Navigation

For the day horizon, provide a time slider.

Example:

```text
06:00 -----------●------------------ 23:00
                  08:15
```

Prefer 15-minute steps.

Add optional playback:

```text
Play / Pause
```

Playback advances the selected time and updates the map.

This is an important demo feature.

Target roughly:

```text
1 UI second = 15 or 30 simulated minutes
```

Make playback speed easy to change in code.

---

# 21. Map Encoding

## 21.1 Route segments

Route segments should encode predicted load.

Suggested normalized load:

```text
0.0 = empty
1.0 = nominal capacity
>1.0 = overloaded
```

Suggested categories:

```text
< 0.30
0.30 - 0.60
0.60 - 0.80
0.80 - 1.00
> 1.00
```

Use a perceptually clear sequential-to-warning scale.

Do not encode everything using color alone; also slightly change line width for selected or overloaded segments.

---

## 21.2 Stops

Show stops as circles.

Possible encodings:

```text
circle radius  -> passenger boardings
circle color   -> load or deviation
```

Avoid making all stops large at low zoom.

Scale or hide minor stop markers depending on zoom.

---

# 22. Interaction

Implement:

## Hover on route segment

Show:

```text
Route 17
08:15
Estimated load: 78%
Prediction interval: 69-88%
```

## Click route segment

Select the route and open/update the bottom detail chart.

## Hover stop

Show:

```text
Stop name
Routes: 17, 38
Predicted boardings: 143 / 15 min
```

## Click stop

Select the stop and show its time-series forecast.

---

# 23. Chart

Use Apache ECharts.

The lower panel should display the selected route/stop time series.

For route load:

```text
x = time
y = predicted load
```

Show:

```text
P50 line
P10-P90 shaded interval
```

For stop demand:

```text
x = time
y = predicted boardings
```

The chart should synchronize visually with the selected map time.

Display a vertical cursor or highlighted data point corresponding to the current time.

---

# 24. Loading and Error States

Even static JSON loading should be treated as asynchronous.

Use TanStack Query.

Provide:

- loading skeleton;
- map overlay spinner only when necessary;
- friendly error message;
- retry button.

The UI should not crash if one data file fails.

---

# 25. Responsive Behavior

Primary target:

```text
desktop / laptop
```

because dispatch dashboards are likely desktop-oriented.

Still ensure the layout remains usable around:

```text
1280 x 720
```

At narrower widths:

- collapse filter sidebar into a drawer;
- keep the map visible;
- allow the chart panel to reduce in height.

Mobile support is not a major requirement.

---

# 26. Performance Requirements

Avoid rerendering all map features through React whenever time changes.

Prefer:

- MapLibre source data updates;
- feature-state where appropriate;
- memoized derived data;
- stable GeoJSON geometry;
- updating only forecast properties when possible.

Do not recreate the entire map instance for each filter update.

Do not store large immutable geometry objects in rapidly changing React state.

---

# 27. Data Separation

Keep static geometry and time-varying predictions separate.

Good:

```text
tram_routes.geojson
tram_stops.geojson

route_forecasts.json
stop_forecasts.json
```

Avoid creating one giant GeoJSON file with a copy of every route geometry for every timestamp.

The frontend should join forecasts to geometry using stable IDs.

---

# 28. Docker Requirements

Create a production-style Docker image.

Recommended multi-stage build:

```text
Stage 1:
Node
npm ci
npm run build

Stage 2:
nginx
copy dist/
copy nginx.conf
```

The final image should not contain the full Node development environment.

Expected command:

```bash
docker build -t tram-forecast-frontend ./frontend
docker run --rm -p 8080:80 tram-forecast-frontend
```

Then:

```text
http://localhost:8080
```

must open the application.

Also provide root `docker-compose.yml`.

For now it may contain only the frontend service.

Example conceptual shape:

```yaml
services:
  frontend:
    build: ./frontend
    ports:
      - "8080:80"
```

Leave room to later add:

```text
backend
postgres
ml-worker
```

---

# 29. Development Workflow

Provide npm scripts such as:

```text
npm run dev
npm run build
npm run lint
npm run typecheck
```

Optionally:

```text
npm run test
```

Use ESLint.

Use formatting tooling such as Prettier if desired.

---

# 30. Offline OSM Utility

`tools/osm/README.md` must explain:

- what the script downloads;
- which OSM/Overpass source is used;
- how to execute it;
- where the output is written;
- that it is not required during normal runtime.

Example:

```bash
python tools/osm/fetch_osm_trams.py \
  --city "Moscow" \
  --output tmp/moscow_trams.json

python tools/osm/normalize_osm.py \
  --input tmp/moscow_trams.json \
  --output frontend/public/data/osm
```

If reliable relation reconstruction is difficult, it is acceptable for the first implementation to:

1. retrieve tram rails;
2. retrieve tram stops;
3. save them separately;
4. use synthetic route IDs for demonstration.

But keep the importer modular so route relations can later be added.

---

# 31. Mock Data Utility

`tools/mock-data/README.md` must explain how to regenerate forecast fixtures.

Example:

```bash
python tools/mock-data/generate_forecasts.py \
  --osm-dir frontend/public/data/osm \
  --output frontend/public/data/mock \
  --seed 42
```

The generator should use the existing OSM output when possible.

It should inspect:

```text
route IDs
stop IDs
segment IDs
```

and generate predictions for those exact IDs.

Do not make the frontend depend on hardcoded route names.

---

# 32. Mock Generator Pseudocode

Conceptual structure:

```python
rng = np.random.default_rng(seed)

for route in routes:
    params = create_route_parameters(route.id, rng)

    for horizon in ["day", "month", "year"]:
        timestamps = make_timestamps(horizon)

        for timestamp in timestamps:
            base = params.base_demand

            hour = decimal_hour(timestamp)

            morning = gaussian(
                hour,
                params.morning_peak_time,
                params.morning_peak_width,
            )

            evening = gaussian(
                hour,
                params.evening_peak_time,
                params.evening_peak_width,
            )

            weekday_factor = ...
            seasonal_factor = ...

            demand = (
                base
                + params.morning_peak_amplitude * morning
                + params.evening_peak_amplitude * evening
            )

            demand *= weekday_factor
            demand *= seasonal_factor

            demand *= 1 + rng.normal(0, params.noise)

            save_route_prediction(...)
```

For each segment:

```python
position = segment_index / max(1, segment_count - 1)

profile = 0.4 + 0.9 * np.sin(np.pi * position) ** route_shape

segment_load = route_demand * profile / route_capacity
```

Clamp values to a reasonable range, for example:

```text
0.0 to 1.4
```

Allow overloads above 1.0 for visual demonstration.

---

# 33. Deterministic Route Parameters

It is useful for each route to have a stable personality.

Examples:

```text
Route 17:
    strong morning commute peak
    medium evening peak

Route 38:
    balanced two-peak profile

Route 6:
    flatter all-day demand

Route 50:
    stronger evening peak
```

Do not hard-code these exact route numbers if the downloaded data differs.

Instead derive stable route parameters from:

```text
global seed + route ID hash
```

That way a particular route receives the same synthetic parameters every time.

---

# 34. Future ML Integration

The frontend should not know which ML model produced the data.

Later, the ML layer may use:

```text
CatBoost
LightGBM
XGBoost
Temporal Fusion Transformer
N-BEATS
LSTM
Transformer-based forecasting
hybrid statistical / ML models
```

The frontend contract should remain the same.

Store metadata such as:

```text
modelVersion
generatedAt
trainingWindow
predictionHorizon
```

when a real model is introduced.

---

# 35. Important Modeling Caveat

Passenger validations generally represent boardings, not necessarily onboard vehicle occupancy.

Therefore distinguish conceptually between:

```text
predicted boardings
```

and:

```text
estimated onboard load
```

If the future dataset lacks alighting events or origin-destination reconstruction, onboard load must be estimated.

Possible future approaches include:

- trip chaining;
- inferred origin-destination matrices;
- historical destination probabilities;
- route terminal constraints;
- passenger-card sequence analysis.

The UI should avoid presenting inferred load as exact measured occupancy.

Use wording such as:

```text
Estimated vehicle load
```

when appropriate.

---

# 36. Suggested UI Components

Create reusable components such as:

```text
AppShell
ForecastMap
MapLegend
RouteSelector
ForecastHorizonSelector
DateSelector
TimeSlider
PlaybackControls
MetricSelector
ForecastChart
StopPopup
SegmentPopup
StatusBadge
LoadingOverlay
```

Keep business logic outside presentational components.

---

# 37. State Model

At minimum the application state will contain:

```text
selectedRouteId
selectedStopId
selectedSegmentId
selectedHorizon
selectedDate
selectedTimestamp
selectedMetric
isPlaying
```

URL query parameters may later be used for shareable views, but are optional for the first version.

---

# 38. Recommended Metrics

Expose at least:

```text
Estimated load
Boardings
```

Optional:

```text
Deviation from normal
Forecast uncertainty
```

For mock data, "deviation from normal" can be:

```text
(current prediction - route baseline) / route baseline
```

---

# 39. Legend

Always provide a visible legend.

Example:

```text
Estimated load

0-30%       Low
30-60%      Moderate
60-80%      Busy
80-100%     Very busy
100%+       Over capacity
```

Do not make users infer color meaning.

---

# 40. Small Demo Features With High Value

If time permits, implement:

## A. Animation

Play forecast through the day.

## B. Route isolation

Click a route and fade unrelated routes.

## C. Peak-jump buttons

Example:

```text
Morning peak
Evening peak
```

## D. Uncertainty toggle

Show/hide uncertainty intervals on charts.

## E. Demo preset

A "Demo" button may automatically choose:

```text
busy route
weekday
08:15
day horizon
```

This is useful during a live hackathon presentation.

---

# 41. Features to Avoid in the First Version

Do not spend time on:

- authentication;
- user accounts;
- SSR;
- Kubernetes;
- WebSockets;
- Redis;
- full vector-tile infrastructure;
- real-time GPS streaming;
- editable OSM geometry;
- complicated map drawing tools;
- Redux;
- backend mock server unless static repository abstraction proves insufficient.

The goal is a polished visualization with clean architecture, not infrastructure for its own sake.

---

# 42. Future Production Improvements

Later iterations may add:

```text
Spring Boot backend
PostgreSQL + PostGIS
Redis caching
real ML prediction pipeline
scheduled dataset refresh
data-quality checks
real-time telemetry
WebSocket / SSE updates
vector tiles
deck.gl
monitoring / observability
authentication / RBAC
```

---

# 43. Optional deck.gl Upgrade

Do not make deck.gl a dependency for the initial implementation.

If extra time remains, deck.gl may be added for:

- animated vehicle movements;
- trajectory visualization;
- dense point clouds;
- heatmaps;
- flow animations.

MapLibre alone should be sufficient for the first version.

---

# 44. Acceptance Criteria

The implementation is successful when:

1. The repository builds without a backend.
2. `docker compose up --build` starts the application.
3. The app is reachable at `http://localhost:8080`.
4. The map loads centered on Moscow.
5. Tram geometry is loaded from local GeoJSON files.
6. Forecast data is loaded from local generated JSON files.
7. The user can switch between:
   - day;
   - month;
   - year.
8. The user can select a route.
9. The user can select a tram stop.
10. The user can move through time.
11. The route visualization changes as selected time changes.
12. Stops display plausible synthetic demand.
13. Route segments display plausible synthetic load.
14. A bottom chart displays the selected route/stop forecast.
15. Day forecasts show clear morning and evening peaks.
16. Weekend behavior differs from weekday behavior.
17. Long-range forecasts show smooth seasonality.
18. Forecast uncertainty increases with horizon.
19. The frontend data source is isolated behind a repository/service abstraction.
20. The codebase contains reusable offline utilities for:
    - OSM refresh;
    - mock forecast regeneration.

---

# 45. Codex Implementation Order

Implement in approximately this order:

```text
1. Create Vite + React + TypeScript project.
2. Add Mantine and base application shell.
3. Add MapLibre map centered on Moscow.
4. Create sample local GeoJSON if real OSM data is not yet available.
5. Implement OSM offline import utility.
6. Generate normalized tram geometry files.
7. Implement mock forecast generator.
8. Generate deterministic development predictions.
9. Define TypeScript domain models.
10. Create ForecastRepository abstraction.
11. Implement StaticForecastRepository.
12. Load geometry and forecasts with TanStack Query.
13. Render tram routes.
14. Render stops.
15. Add forecast horizon selector.
16. Add date/time controls.
17. Connect route colors to current prediction values.
18. Connect stop size/color to current predictions.
19. Add route/stop selection and hover tooltips.
20. Add ECharts forecast panel.
21. Add uncertainty band.
22. Add playback animation.
23. Add loading/error states.
24. Polish responsive layout.
25. Add Dockerfile + nginx config.
26. Add docker-compose.yml.
27. Verify production build inside Docker.
28. Document local development and data regeneration.
```

---

# 46. Implementation Principle

Prefer a small, clean, runnable system over a large incomplete one.

The current version should be:

```text
real map
+
real tram geometry
+
synthetic predictions
+
polished UI
+
clean replacement path for a future backend
```

The synthetic data layer is temporary.

The user-facing visualization architecture should not be temporary.
