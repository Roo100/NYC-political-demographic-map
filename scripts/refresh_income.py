"""Validate and publish the newest official ACS5 county income table.

No API key or third-party dependencies. Errors preserve the existing snapshot.
"""
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CATALOG = 'https://www2.census.gov/programs-surveys/acs/summary_file/'
COUNTIES = {
    '36005': ('Bronx', 'Bronx County'),
    '36047': ('Brooklyn', 'Kings County'),
    '36061': ('Manhattan', 'New York County'),
    '36081': ('Queens', 'Queens County'),
    '36085': ('Staten Island', 'Richmond County'),
}


def fetch(url, allow_missing=False):
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers={'User-Agent': 'NYC-political-dashboard-income-refresh/1.0'}), timeout=90) as response:
                return response.read()
        except HTTPError as error:
            if allow_missing and error.code == 404:
                return None
            if attempt == 2:
                raise
        except Exception:
            if attempt == 2:
                raise
        time.sleep(2 ** attempt)


def extract(raw, year):
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')), delimiter='|')
    assert {'GEO_ID', 'B19013_E001', 'B19013_M001'}.issubset(reader.fieldnames), 'Income table schema changed'
    found = {}
    for row in reader:
        geoid = row['GEO_ID']
        if geoid not in {'0500000US' + code for code in COUNTIES}:
            continue
        code = geoid.removeprefix('0500000US')
        assert code not in found, 'Duplicate county row'
        estimate = int(row['B19013_E001'])
        moe = int(row['B19013_M001'])
        assert estimate > 0 and moe >= 0, 'Missing or invalid published estimate/MOE'
        borough, county = COUNTIES[code]
        found[code] = {
            'borough': borough, 'county': county, 'state_fips': '36', 'county_fips': code[-3:],
            'county_geoid': code, 'census_geo_id': geoid,
            'median_household_income': estimate, 'margin_of_error_90': moe,
            'reference_period': f'{year-4}–{year}', 'dollar_year': year,
            'table': 'B19013', 'estimate_field': 'B19013_E001', 'moe_field': 'B19013_M001',
        }
    assert set(found) == set(COUNTIES), 'All five NYC counties are required'
    return [found[code] for code in COUNTIES]


def main():
    output = ROOT / 'data/income_latest.json'
    previous = json.loads(output.read_text()) if output.exists() else None
    floor = previous['release_year'] if previous else 2024
    listing = fetch(CATALOG).decode()
    years = sorted({int(y) for y in re.findall(r'href="(20\d{2})/"', listing) if int(y) >= floor}, reverse=True)
    assert years, 'No compatible Census release directories were discovered'
    for year in years:
        url = f'{CATALOG}{year}/table-based-SF/data/5YRData/acsdt5y{year}-b19013.dat'
        raw = fetch(url, allow_missing=True)
        if raw is None:
            continue  # A year directory may exist before its five-year release.
        rows = extract(raw, year)  # A malformed new release must fail, not silently downgrade.
        break
    else:
        raise RuntimeError('No published five-year income release at or after the stored release')
    payload = {
        'release_year': year, 'reference_period': f'{year-4}–{year}', 'dollar_year': year,
        'survey': 'American Community Survey 5-year estimates', 'table': 'B19013',
        'geography': 'NYC counties / boroughs', 'geographic_summary_level': '050',
        'source': 'U.S. Census Bureau, ACS five-year detailed tables',
        'source_url': url, 'table_url': f'https://data.census.gov/table/ACSDT5Y{year}.B19013',
        'source_sha256': hashlib.sha256(raw).hexdigest(), 'catalog_url': CATALOG,
        'checked_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'rows': rows,
    }
    stream = io.StringIO()
    csv_rows = [dict(row, source_url=url, checked_at=payload['checked_at'], source_sha256=payload['source_sha256']) for row in rows]
    writer = csv.DictWriter(stream, fieldnames=csv_rows[0])
    writer.writeheader()
    writer.writerows(csv_rows)
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = output.with_suffix('.tmp')
    staging.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
    staging.replace(output)
    (ROOT / 'data/income_latest.csv').write_text(stream.getvalue())
    print(f'Validated ACS {year-4}–{year}: five exact county FIPS matches')
    for row in rows:
        print(f"{row['borough']}: ${row['median_household_income']:,} ± ${row['margin_of_error_90']:,}")


if __name__ == '__main__':
    main()
