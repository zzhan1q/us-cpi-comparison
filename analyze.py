"""Compare four monthly BLS CPI-U series fetched through FRED."""

import csv
from datetime import date
from decimal import Decimal, InvalidOperation
from html import escape
from io import StringIO
import math
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent
FRED = 'https://fred.stlouisfed.org'
SERIES = {
    'CPIAUCNS': ('Все товары и услуги', '#173049', ''),
    'CUUR0000SAF11': ('Продукты для дома', '#a34728', '8 3'),
    'CUUR0000SEHA': ('Аренда основного жилья', '#12736b', '2 3'),
    'CUUR0000SEHF01': ('Электроэнергия', '#624596', '10 3 2 3'),
}
HISTORY = tuple(f'{year}-{month:02d}-01' for year in range(2018, 2025) for month in range(1, 13))
DISPLAY = HISTORY[12:]


def parse_series(text, series_id):
    rows = csv.DictReader(StringIO(text))
    if not {'observation_date', series_id}.issubset(rows.fieldnames or ()):
        raise ValueError(f'{series_id}: unexpected FRED CSV columns')
    values = {}
    for row in rows:
        raw_date = row['observation_date']
        observed = date.fromisoformat(raw_date)
        if not 2018 <= observed.year <= 2024:
            continue
        if observed.day != 1 or raw_date != observed.isoformat():
            raise ValueError(f'{series_id}: not a monthly date: {raw_date}')
        if raw_date in values:
            raise ValueError(f'{series_id}: duplicate month {raw_date}')
        try:
            value = Decimal(row[series_id] or '')
        except InvalidOperation as exc:
            raise ValueError(f'{series_id}: missing or invalid value for {raw_date}') from exc
        if not value.is_finite() or value <= 0:
            raise ValueError(f'{series_id}: nonpositive or nonfinite value for {raw_date}')
        values[raw_date] = value
    missing = sorted(set(HISTORY) - values.keys())
    if missing:
        raise ValueError(f'{series_id}: missing months: {", ".join(missing)}')
    return values


def transform(values):
    base = values[DISPLAY[0]]
    return [(month[:7], values[month] / base * 100,
             (values[month] / values[HISTORY[i]] - 1) * 100)
            for i, month in enumerate(DISPLAY)]


def line_chart(data, column, title, unit):
    step = 10 if column == 1 else 5
    values = [float(row[column]) for rows in data.values() for row in rows]
    low = math.floor(min(values) / step) * step
    high = max(low + step, math.ceil(max(values) / step) * step)
    x = lambda i: 55 + i * 680 / 71
    y = lambda v: 204 - (float(v) - low) * 175 / (high - low)
    parts = [f'<svg viewBox="0 0 760 236" role="img" aria-label="{title}"><title>{title}</title>',
             f'<text x="55" y="17">{unit}</text>']
    for tick in range(low, high + 1, step):
        yy = y(tick)
        parts.append(f'<line x1="55" x2="735" y1="{yy:.2f}" y2="{yy:.2f}" class="gridline"/><text x="45" y="{yy + 4:.2f}" text-anchor="end">{tick}</text>')
    for i in range(0, 72, 12):
        parts.append(f'<text x="{x(i):.2f}" y="227" text-anchor="middle">{2019 + i // 12}</text>')
    for key, rows in data.items():
        label, color, dash = SERIES[key]
        points = ' '.join(f'{x(i):.2f},{y(row[column]):.2f}' for i, row in enumerate(rows))
        parts.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-dasharray="{dash or "none"}" stroke-width="2.5" vector-effect="non-scaling-stroke"><title>{label}</title></polyline>')
    return ''.join(parts) + '</svg>'


STYLE = '''
:root{color-scheme:light;--ink:#182735;--muted:#465865;--rule:#cad3d8;--paper:#f3f3ed;--panel:#fff}
*{box-sizing:border-box} body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 'Segoe UI',Arial,sans-serif}
main{width:min(100% - 32px,1020px);margin:auto;padding:32px 0 48px} header{border-top:4px solid var(--ink);padding-top:12px}
.eyebrow{font:700 .78rem/1.4 Consolas,monospace;color:var(--muted);letter-spacing:.1em} h1{font:700 clamp(2rem,5vw,3.4rem)/1.08 Georgia,serif;margin:.35em 0}
h2{font-size:1.23rem;margin:0 0 .65em} p{margin:0 0 .8em} section,figure{margin:20px 0} figure,.sheet{background:var(--panel);border:1px solid var(--rule);padding:clamp(10px,3vw,24px)}
figcaption{font-weight:700} svg{display:block;width:100%;height:auto} svg text{font:13px 'Segoe UI',Arial,sans-serif;fill:var(--muted)} .gridline{stroke:var(--rule)}
.key{display:flex;gap:6px 20px;flex-wrap:wrap;list-style:none;padding:0;margin:10px 0 0;font-size:.9rem}.key i{display:inline-block;width:22px;margin:0 5px 3px 0;border-top:3px solid var(--series)}
.scroller{overflow:auto;max-width:100%} table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums} th,td{border-bottom:1px solid var(--rule);padding:.42rem .56rem;text-align:right} th:first-child{text-align:left} thead{background:#e9eff1} .wide{min-width:680px} a{color:#155868} a:focus-visible,.scroller:focus-visible{outline:2px solid #155868;outline-offset:2px} footer{color:var(--muted);font-size:.9rem} footer a{overflow-wrap:anywhere}
@media(max-width:540px){main{padding-top:18px}svg text{font-size:19px}}
'''


def publish(data, root):
    with (root / 'summary.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(('month', 'series_id', 'index_jan_2019_100', 'yoy_pct'))
        for i, month in enumerate(DISPLAY):
            for key in SERIES:
                _, index, yoy = data[key][i]
                writer.writerow((month[:7], key, f'{index:.4f}', f'{yoy:.4f}'))
    end = {key: rows[-1] for key, rows in data.items()}
    final = ''.join(f'<tr><th scope="row">{SERIES[key][0]}</th><td>{idx - 100:+.2f}%</td><td>{yoy:+.2f}%</td></tr>'
                    for key, (_, idx, yoy) in end.items())
    headings = ''.join(f'<th scope="colgroup" colspan="2">{label}</th>' for label, *_ in SERIES.values())
    details = []
    for i, month in enumerate(DISPLAY):
        cells = ''.join(f'<td>{data[key][i][j]:.2f}</td>' for key in SERIES for j in (1, 2))
        details.append(f'<tr><th scope="row">{month[:7]}</th>{cells}</tr>')
    legend = ''.join(f'<li><i style="--series:{color};border-top-style:{style}"></i>{label}</li>'
                     for (label, color, _), style in zip(SERIES.values(), ('solid', 'dashed', 'dotted', 'dashed')))
    sources = ' · '.join(f'<a href="{escape(FRED + "/series/" + key, quote=True)}">{key}</a>' for key in SERIES)
    page = f'''<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>ИПЦ США: четыре ряда</title><style>{STYLE}</style></head>
<body><main><header><div class="eyebrow">01 / США · CPI-U · 2019–2024</div><h1>Как менялись потребительские цены в США</h1><p>Четыре месячных индекса BLS без сезонной корректировки и сглаживания.</p></header>
<section class="sheet"><h2>Декабрь 2024: два способа сравнения</h2><div class="scroller" tabindex="0" role="region" aria-label="Итоги декабря 2024"><table><thead><tr><th scope="col">Ряд</th><th scope="col">К янв. 2019</th><th scope="col">К дек. 2023</th></tr></thead><tbody>{final}</tbody></table></div></section>
<figure><figcaption>Общая точка отсчёта: январь 2019 = 100</figcaption>{line_chart(data, 1, 'Индексы к январю 2019 года', 'Пункты индекса')}<ul class="key">{legend}</ul></figure>
<figure><figcaption>Изменение к тому же месяцу предыдущего года</figcaption>{line_chart(data, 2, 'Изменение год к году', 'Год к году, %')}<ul class="key">{legend}</ul></figure>
<section class="sheet"><h2>Все 72 месяца</h2><p>В каждой паре столбцов — индекс к январю 2019 и годовое изменение.</p><div class="scroller" tabindex="0" role="region" aria-label="Месячные показатели ИПЦ"><table class="wide"><colgroup span="1"></colgroup>{'<colgroup span="2"></colgroup>' * 4}<thead><tr><th scope="col" rowspan="2">Месяц</th>{headings}</tr><tr>{'<th scope="col">Индекс</th><th scope="col">Г/г, %</th>' * 4}</tr></thead><tbody>{''.join(details)}</tbody></table></div></section>
<footer><p>Источник — U.S. Bureau of Labor Statistics через FRED: {sources}.</p><p>Г/г = 100 × (значение / значение 12 месяцев назад − 1). История 2018 года нужна только для расчёта. Городской CPI-U не описывает расходы конкретной семьи; категории не складываются в общий индекс.</p><a href="summary.csv" download>Скачать расчётный CSV</a></footer></main></body></html>'''
    (root / 'report.html').write_text(page, encoding='utf-8')


def main():
    params = urlencode({'id': ','.join(SERIES), 'cosd': HISTORY[0], 'coed': HISTORY[-1]})
    with urlopen(f'{FRED}/graph/fredgraph.csv?{params}', timeout=60) as response:
        text = response.read().decode('utf-8-sig')
    data = {key: transform(parse_series(text, key)) for key in SERIES}
    publish(data, ROOT)
    print('84 months verified for each of 4 series; 72 published per series.')
    for key, rows in data.items():
        _, index, yoy = rows[-1]
        print(f'{key}: Dec 2024 index={index:.2f}; YoY={yoy:+.2f}%')


if __name__ == '__main__':
    main()
