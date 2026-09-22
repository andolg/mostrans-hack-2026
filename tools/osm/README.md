# Обновление данных OSM

Скрипты запускаются только при подготовке данных. Браузер и Docker-контейнер не обращаются к Overpass API.

`fetch_osm_trams.py` получает отношения `type=route + route=tram` и все входящие в них пути/узлы. Фильтр `--route-ref` можно повторять; без него загружается вся трамвайная сеть в bbox Москвы. `normalize_osm.py` сохраняет каждый входящий в relation путь как отдельный стабильный сегмент и связывает остановки с relation ID. Это сохраняет направления и порядок членов relation, включая маршруты наподобие relation `1284062` (т2).

```powershell
python tools/osm/fetch_osm_trams.py `
  --route-ref t2 --route-ref 6 --route-ref 17 --route-ref 38 `
  --output tmp/moscow_trams.json

python tools/osm/normalize_osm.py `
  --input tmp/moscow_trams.json `
  --output frontend/public/data/osm
```

Источник — публичный Overpass API; данные © OpenStreetMap contributors, ODbL 1.0. Для регулярных или полных выгрузок следует использовать собственный Overpass-инстанс/региональный extract и соблюдать политику использования сервиса.

