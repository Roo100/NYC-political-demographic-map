# Verified county voter enrollment

The dashboard uses the New York State Board of Elections' county enrollment workbook, as of **February 20, 2026**. Counts are **total registrations, including active and inactive records**. Income and other display layers reuse this same verified political context.

## Official sources

- [State enrollment catalog](https://elections.ny.gov/enrollment-county).
- [NYC Board of Elections enrollment catalog](https://vote.nyc/page/voter-enrollment-totals).
- [February 2026 county workbook](https://www.vote.nyc/sites/default/files/pdf/vote/2026/county_feb26.xlsx).

The five county mappings are Bronx to Bronx, Kings to Brooklyn, New York to Manhattan, Queens to Queens, and Richmond to Staten Island. The JSON and CSV record county names, county FIPS, snapshot date, source URL, source SHA-256 and retrieval/check metadata.

The source's DEM, REP, CON, WOR, OTH and BLANK columns are preserved directly. OTH is the published aggregate of other parties, not a single party. BLANK represents voters without party enrollment. All six categories sum to TOTAL. For each county and each column, Active plus Inactive must equal Total before publication.

## Staten Island correction

| Enrollment category | Verified total |
|---|---:|
| Democratic | 130,454 |
| Republican | 109,043 |
| Conservative | 4,373 |
| Working Families | 1,274 |
| Other parties | 8,064 |
| Unaffiliated / blank | 86,054 |
| All registrations | 339,262 |

Democratic is the largest enrollment category at approximately 38.5% of registrations. The label is **Largest voter enrollment group**. It describes a plurality of registrations, not a majority, an election result, ideology or likely turnout.

## Removed failure paths

The old browser parser scanned only 120 rows after a header. The February 2026 workbook's NYC county rows occur much later, so it could miss all five and activate unverified fallback estimates. Those estimates and the browser-side workbook dependency are removed. The validated extraction now scans every worksheet row, requires all five counties and all three statuses, rejects duplicate records, and reconciles the category and status totals.

Browsers fetch the validated same-origin snapshot with cache-busting, avoiding a cross-origin workbook dependency. Invalid or unavailable enrollment yields unavailable counts and no leading group. Missing enrollment is never converted to a Democratic leader or to zero counts.

## Daily refresh

The GitHub Actions workflow **Refresh verified voter enrollment** checks the official catalogs daily at 10:57 UTC and can run manually. It discovers advertised county workbooks, reads the actual registration date inside the workbook, and rejects older or inconsistent releases. A failed official download or failed validation does not overwrite the last verified snapshot. Data remains dated to its actual publication, independently of the daily check date.

The app displays the last successful check and flags checks older than three days. The workflow commits verified JSON/CSV and requests a GitHub Pages rebuild. The income refresh remains separate. Race and education retain their existing independent source/fallback behavior.

Reproduce using Python 3.12: `python scripts/refresh_enrollment.py`. No API key or third-party packages are required.
