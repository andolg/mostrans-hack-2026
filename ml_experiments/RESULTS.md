# Эксперименты по прогнозу посадок

## Данные и подготовка

Цель — число успешных валидаций (`validation_result == 1`) для каждой тройки
`route × date × hour`. Маршрут берётся из `ngpt_route`, время — из
`tran_date_time`. `input_date_time` ненадёжен; `place_id` обозначает площадку,
а не остановку. Отсутствующие часы заполняются нулями. Маршрут 5 входит в
обязательную сетку, но не имеет успешных валидаций в выданной истории.

`prepare.py` читает сырые CSV порциями, фильтрует даты по времени самой
валидации и сохраняет полную почасовую сетку. Получено 72 960 строк за
январь–октябрь 2025 и 59 667 191 посадка. Все 72 960 значений **в точности**
совпали с предоставленными `labels_day_train.csv` и `labels_day_test.csv`
после дополнения отсутствующих часов нулями. Сырые CSV занимают около 10,4 ГБ.

## Оценка

Метрика организаторов: `WAPE-score = max(0, 1 - sum(abs(y-pred)) / sum(y))`.
Каждый прогон обучен только на датах до границы и предсказывает следующие два
месяца целиком. Оценка проводится по полной сетке, включая нулевые часы.

| Модель | Май–июнь | Июль–август | Сентябрь–октябрь |
| --- | ---: | ---: | ---: |
| Медиана того же маршрута, дня недели и часа за 12 недель | 0.80266 | 0.76696 | 0.79847 |
| LightGBM, MAE | 0.79702 | 0.81053 | 0.80099 |
| LightGBM, Poisson | 0.76666 | 0.78098 | 0.82283 |
| LightGBM, MAE, более глубокие деревья | 0.76578 | 0.82207 | **0.82698** |
| CatBoost, MAE | 0.75748 | 0.70697 | 0.77937 |
| Выбранный ансамбль | 0.78087 | **0.82973** | 0.82488 |

Испробованы также медиана за 4/8 недель, среднее за 8 недель, LightGBM с
обучением только на последних 120/180 днях и CatBoost с RMSE. Полные результаты
и почасовые предсказания находятся в `../untracked/data/experiments/initial/`
и `../untracked/data/experiments/more/`.

Для финального прогноза выбран ансамбль: 70% глубокий LightGBM MAE, 10%
LightGBM Poisson, 20% медиана за 12 недель. Он показал более ровный результат
на трёх временных окнах, сохранив 0.82488 на последнем, наиболее близком к
целевому периоду. Пример организаторов имеет заявленный score около 0.48,
но его оценка относится к скрытому периоду и напрямую с этой таблицей не
сопоставима.

## Артефакты и запуск

Из корня репозитория:

```powershell
cd ml_experiments
$env:UV_CACHE_DIR = (Join-Path (Resolve-Path ..) 'untracked/uv-cache')
uv sync
uv run python prepare.py --input ../untracked/data/dataset/train.csv --input ../untracked/data/dataset/test.csv --output ../untracked/data/hourly_2025_jan_oct.csv --start 2025-01-01 --end 2025-10-31
uv run python evaluate.py --data ../untracked/data/hourly_2025_jan_oct.csv --output ../untracked/data/experiments/initial
uv run python evaluate_more.py --data ../untracked/data/hourly_2025_jan_oct.csv --output ../untracked/data/experiments/more
uv run python forecast.py --data ../untracked/data/hourly_2025_jan_oct.csv --output ../untracked/data/submission.csv --models-dir ../untracked/data/experiments/final
uv run python predict_saved.py --models-dir ../untracked/data/experiments/final --output ../untracked/data/reloaded_submission.csv --start 2025-11-01 --end 2025-12-31
```

Готовый `../untracked/data/submission.csv` содержит 14 640 строк полного
ноябрьско-декабрьского грида с колонками
`route;date;hour;prediction`; сумма прогнозов — 12 063 819.
В `../untracked/data/experiments/final/` лежат обученные модели, сезонный
профиль и параметры ансамбля. `predict_saved.py` воспроизводит `submission.csv`
побайтно без переобучения. Все пути входа и выхода задаются аргументами
командной строки.

Ноябрь и декабрь недоступны для проверки, поэтому score финального файла
неизвестен. Модель опирается на календарь и прошлые валидации; изменения
маршрутов, погода и события могут ухудшить прогноз. Цель измеряет посадки,
а не фактическую заполненность салона.
