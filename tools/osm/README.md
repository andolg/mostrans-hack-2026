# Обновление данных OSM

Скрипты запускаются только при подготовке данных. Браузер и контейнеры приложения во время работы не обращаются к Overpass API.

`fetch_osm_trams.py` получает отношения `type=route + route=tram` и все входящие в них пути/узлы. `--route-refs` принимает список через пробел; без фильтра загружается вся трамвайная сеть в bbox Москвы. `normalize_osm.py` сохраняет каждый входящий в relation путь как отдельный стабильный сегмент и связывает остановки с relation ID.

По умолчанию загрузчик использует `https://overpass-api.de/api/interpreter`. Для примера ниже выбран `https://overpass.private.coffee/api/interpreter` через `--endpoint`: он может понадобиться при ошибке 504 на основном сервере. Оба адреса — публичные экземпляры Overpass и могут быть недоступны или отвечать с задержкой; загрузчик не переключается между ними автоматически.

Маршруты из задания: `1, 5, 7, 11, 12, 17, 25, 26, 28, 50`. Загрузить и нормализовать их одной командой на каждом этапе:

```powershell
python tools/osm/fetch_osm_trams.py `
  --route-refs 1 5 7 11 12 17 25 26 28 50 `
  --endpoint https://overpass.private.coffee/api/interpreter `
  --output tmp/moscow_trams.json

python tools/osm/normalize_osm.py `
  --input tmp/moscow_trams.json `
  --output frontend/public/data/osm
```

Источник — публичный Overpass API; данные © OpenStreetMap contributors, ODbL 1.0. Для регулярных или полных выгрузок следует использовать собственный Overpass-инстанс/региональный extract и соблюдать политику использования сервиса.
