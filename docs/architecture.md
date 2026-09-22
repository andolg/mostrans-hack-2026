# Архитектура

```text
Overpass API (offline) ──> fetch ──> normalize ──> GeoJSON
                                                   │
GeoJSON ──> synthetic generator ──> compact JSON   │
                                      │            │
                                      v            v
Browser ──> ForecastRepository ──> TanStack Query ──> map + charts
```

## Runtime

Vite собирает React SPA, nginx раздаёт её и `/data/*`. `StaticForecastRepository` — единственная точка чтения JSON/GeoJSON. UI не знает, статичен ли источник: будущий `ApiForecastRepository` реализует тот же контракт для Spring Boot API.

Геометрия и значения прогноза разделены. При движении слайдера карта получает стабильные объекты линий/точек с обновлёнными forecast-свойствами; экземпляр MapLibre не пересоздаётся.

## OSM-модель

Первичный объект маршрута — OSM relation `type=route`, `route=tram`. ID направления нормализуется как `osm-rel:{relationId}`. Каждый упорядоченный way-член relation становится GeoJSON LineString с устойчивым `segmentId`. Остановки берутся из relation members (`stop`, `platform`, entry/exit variants), а импортёр дополнительно понимает распространённые `railway` и `public_transport` tags.

Выбор relation ID вместо одного `ref` принципиален: два направления с одинаковым номером могут иметь отличающиеся трассы и порядок остановок.

## Прогноз

Маршрутный ряд хранится явно. Для каждого сегмента хранится только плавный профиль позиции на маршруте. Для остановки хранится коэффициент притяжения и набор route IDs; её ряд выводится в репозитории. При переходе на backend эти вычисления можно перенести серверно без изменения domain types и UI.

`predictedBoardings` — прогноз посадок. `predictedLoad` — оценка загрузки, нормированная на вместимость; она намеренно подписана как оценочная.

