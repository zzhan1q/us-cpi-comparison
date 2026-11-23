import csv
import io
import tempfile
import unittest
from pathlib import Path

import analyze as a


def fixture(overrides=None, extra=()):
    overrides = overrides or {}
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(['observation_date', 'TEST'])
    for year in range(2018, 2025):
        for month in range(1, 13):
            date = f'{year}-{month:02d}-01'
            value = overrides.get(date, 80 if year == 2018 else 100)
            if value is not None:
                writer.writerow([date, value])
    writer.writerows(extra)
    return stream.getvalue()


class AnalysisTests(unittest.TestCase):
    def test_rebased_and_yoy_use_distinct_denominators(self):
        values = a.parse_series(fixture({'2024-12-01': 150, '2023-12-01': 125}), 'TEST')
        rows = a.transform(values)
        self.assertEqual(len(rows), 72)
        self.assertEqual(rows[0], ('2019-01', 100, 25))
        self.assertEqual(rows[-1], ('2024-12', 150, 20))

    def test_missing_history_fails(self):
        with self.assertRaisesRegex(ValueError, '2018-02'):
            a.parse_series(fixture({'2018-02-01': None}), 'TEST')

    def test_duplicate_month_fails(self):
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            a.parse_series(fixture(extra=[('2019-01-01', 100)]), 'TEST')

    def test_invalid_in_window_values_fail(self):
        for value in ('.', '', 'nan', 'inf', 0, -1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                a.parse_series(fixture({'2019-03-01': value}), 'TEST')

    def test_outside_window_ignored(self):
        series = a.parse_series(fixture(extra=[('2025-01-01', '.'), ('2017-12-01', '')]), 'TEST')
        self.assertEqual(len(series), 84)

    def test_off_month_date_in_window_fails(self):
        with self.assertRaises(ValueError):
            a.parse_series(fixture(extra=[('2024-12-02', 100)]), 'TEST')

    def test_outputs_contain_only_display_metrics(self):
        data = {key: a.transform(a.parse_series(fixture(), 'TEST')) for key in a.SERIES}
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            root = Path(directory)
            a.publish(data, root)
            with (root / 'summary.csv').open(encoding='utf-8', newline='') as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 288)
            self.assertEqual(set(rows[0]), {'month', 'series_id', 'index_jan_2019_100', 'yoy_pct'})
            html = (root / 'report.html').read_text(encoding='utf-8')
            self.assertIn('<svg', html)
            self.assertIn('<table', html)
            self.assertNotIn('2018-01', html)
