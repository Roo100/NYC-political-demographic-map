# Borough income source and refresh

Income is the U.S. Census Bureau's **2020–2024 ACS five-year median household income**, in **2024 inflation-adjusted dollars**, from **table B19013**. Its 90% margin of error is shown in borough cards, income rankings, and the income CSV. This is an annual household-income estimate for a five-year reference period, not current-year income or individual earnings.

## Official data

- [Census table B19013, 2024 five-year release](https://data.census.gov/table/ACSDT5Y2024.B19013).
- [Published table-based summary file](https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/data/5YRData/acsdt5y2024-b19013.dat).
- [Official ACS summary-file documentation](https://www.census.gov/programs-surveys/acs/data/summary-file.html).

The pipe-delimited summary file supplies GEO_ID, B19013_E001 (estimate), and B19013_M001 (90% margin of error). These correspond to Census API variables B19013_001E and B19013_001M. The refresh downloads the official published file directly, avoiding an API-key dependency in visitors' browsers. The snapshot includes the source URL and complete downloaded source file's SHA-256.

## Geographic matching

This dashboard maps boroughs. Each borough matches one county; income is selected by the Census county GEO_ID at summary level 050. No neighborhood estimates, NTA crosswalks, averages of medians, or name-based guesses are used.

| Borough | County | County FIPS | Census GEO_ID |
|---|---|---|---|
| Bronx | Bronx | 36005 | 0500000US36005 |
| Brooklyn | Kings | 36047 | 0500000US36047 |
| Manhattan | New York | 36061 | 0500000US36061 |
| Queens | Queens | 36081 | 0500000US36081 |
| Staten Island | Richmond | 36085 | 0500000US36085 |

The app requires all five boroughs in the boundary dataset and validates all five income records before using them. Income describes all households in the county. Party enrollment describes enrolled voters and is a different population. The income display bands are fixed visualization thresholds, not official socioeconomic class definitions.

## Automatic refresh

The workflow **Refresh official borough income** runs daily at 10:37 UTC, on manual request, or when its refresh code changes. It discovers available year directories in the official Census summary-file catalog and checks the newest five-year B19013 file. A year directory without a five-year file (HTTP 404) is skipped because one-year tables can be published earlier. Other network failures, malformed new releases, missing counties, duplicate records, missing estimates and missing margins of error fail the job and preserve the existing snapshot. A release older than the stored release is never selected.

After validation, the workflow saves data/income_latest.json and data/income_latest.csv, commits them, and requests a GitHub Pages rebuild. The app fetches the snapshot with a cache-busting URL on every visit. It displays the reference period, dollar year and last successful source check in New York time. A check older than three days is visibly flagged as overdue. ACS releases new observations annually; the daily job checks for publications and corrections.

The last validated snapshot stays available if the Census source is temporarily unavailable. If the dashboard's snapshot itself is unavailable or invalid, income remains unavailable, map areas are gray, and no invented income fallback or zero-income replacement is used. Download is disabled until verified income loads.

## Scope and reproduction

The previous hard-coded income fallback has been removed. Voter enrollment, race/ethnicity and education retain their existing independent source and fallback behavior and are not certified by this income correction. Their source labels remain visible in the dashboard.

Run `python scripts/refresh_income.py` with Python 3.12 and network access. No third-party packages or API key are needed. Inspect workflow history and the snapshot's release_year, reference_period, dollar_year, checked_at, source_url and source_sha256 for provenance.
