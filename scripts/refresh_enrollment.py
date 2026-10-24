"""Publish verified NYS BOE county enrollment; never substitute estimates."""
from datetime import datetime, timezone
import csv
import hashlib
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import re
import time
from urllib.parse import urljoin
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
COUNTIES = {'Bronx':('Bronx','36005'), 'Kings':('Brooklyn','36047'), 'New York':('Manhattan','36061'), 'Queens':('Queens','36081'), 'Richmond':('Staten Island','36085')}
FIELDS = ['DEM','REP','CON','WOR','OTH','BLANK','TOTAL']
NS = {'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
CATALOGS = ['https://elections.ny.gov/enrollment-county','https://vote.nyc/page/voter-enrollment-totals']


def fetch(url):
    for attempt in range(2):
        try:
            with urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; NYC-enrollment-data-check/1.0)'}),timeout=30) as response:
                return response.read()
        except Exception:
            if attempt == 1:
                raise
            time.sleep(1)


class Links(HTMLParser):
    def __init__(self):
        super().__init__();self.href=None;self.text=[];self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag=='a':self.href=dict(attrs).get('href');self.text=[]
    def handle_data(self,data):
        if self.href:self.text.append(data)
    def handle_endtag(self,tag):
        if tag=='a' and self.href:self.links.append((self.href,' '.join(self.text)));self.href=None


def discover():
    candidates={}
    for catalog in CATALOGS:
        try:
            parser=Links();parser.feed(fetch(catalog).decode())
            for href,label in parser.links:
                url=urljoin(catalog,href)
                if 'voters-registered-county-' in href:
                    date=re.search(r'(\d{1,2}/\d{1,2}/\d{4})',label)
                    if date:candidates[url]=datetime.strptime(date[1],'%m/%d/%Y').date().isoformat()
                elif re.search(r'county_[a-z]{3}\d{2}\.xlsx',href,re.I):
                    date=re.search(r'county_([a-z]{3})(\d{2})\.xlsx',href,re.I)
                    candidates[url]=datetime.strptime(date[1]+date[2],'%b%y').date().isoformat()
        except Exception as error:
            print(f'Catalog unavailable: {catalog}: {error}')
    assert candidates,'No official enrollment workbooks discovered'
    return sorted(candidates.items(),key=lambda pair:pair[1],reverse=True)


def extract(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        strings=[''.join(n.itertext()) for n in ET.fromstring(archive.read('xl/sharedStrings.xml')).findall('s:si',NS)]
        all_rows=[]
        for name in archive.namelist():
            if not re.fullmatch(r'xl/worksheets/sheet\d+\.xml',name):continue
            rows=[]
            for element in ET.fromstring(archive.read(name)).findall('.//s:row',NS):
                row={}
                for cell in element.findall('s:c',NS):
                    value=cell.find('s:v',NS)
                    if value is not None:row[re.sub(r'\d','',cell.attrib['r'])]=strings[int(value.text)].strip() if cell.attrib.get('t')=='s' else value.text
                rows.append(row)
            all_rows.extend(rows)
    text=' '.join(str(v) for row in all_rows for v in row.values())
    match=re.search(r'Voters Registered as of\s+([A-Za-z]+ \d{1,2}, \d{4})',text)
    assert match,'Missing official registration snapshot date'
    as_of=datetime.strptime(match[1],'%B %d, %Y').date().isoformat()
    header=None;found={}
    for row in all_rows:
        if {'COUNTY','STATUS',*FIELDS}.issubset(set(str(v).upper() for v in row.values())):
            header={str(v).upper():k for k,v in row.items()};continue
        if not header:continue
        county=row.get(header['COUNTY'],'').strip();status=row.get(header['STATUS'],'').strip().lower()
        if county not in COUNTIES or status not in ['active','inactive','total']:continue
        key=(county,status);assert key not in found,'Duplicate county/status record'
        values={field:int(str(row.get(header[field],'')).replace(',','')) for field in FIELDS}
        assert all(v>=0 for v in values.values()) and sum(values[f] for f in FIELDS if f!='TOTAL')==values['TOTAL'],'Party counts do not reconcile to total'
        found[key]=values
    rows=[]
    for county,(borough,fips) in COUNTIES.items():
        assert all((county,status) in found for status in ['active','inactive','total']),'Missing county/status'
        assert all(found[county,'active'][f]+found[county,'inactive'][f]==found[county,'total'][f] for f in FIELDS),'Active/inactive reconciliation failed'
        rows.append(dict(borough=borough,county=county,county_geoid=fips,**found[county,'total']))
    return as_of,rows


def main():
    output=ROOT/'data/enrollment_latest.json'
    previous=json.loads(output.read_text()) if output.exists() else None
    candidates=discover();latest=candidates[0][1];errors=[]
    for url,inferred_date in candidates:
        if previous and inferred_date[:7]<previous['as_of'][:7]:continue
        try:
            raw=fetch(url);as_of,rows=extract(raw)
            assert as_of>=latest,'Workbook predates the newest advertised official release'
            assert not previous or as_of>=previous['as_of'],'Refusing older enrollment data'
            break
        except Exception as error:errors.append(f'{url}: {error}')
    else:raise RuntimeError('No current validated official enrollment workbook: '+'; '.join(errors))
    payload=dict(as_of=as_of,status='Total (active + inactive)',source='New York State Board of Elections',source_url=url,catalog_urls=CATALOGS,source_sha256=hashlib.sha256(raw).hexdigest(),checked_at=datetime.now(timezone.utc).isoformat(timespec='seconds'),rows=rows)
    stream=io.StringIO();flat=[dict(row,as_of=as_of,status=payload['status'],source_url=url,source_sha256=payload['source_sha256'],checked_at=payload['checked_at']) for row in rows]
    writer=csv.DictWriter(stream,fieldnames=flat[0]);writer.writeheader();writer.writerows(flat)
    output.parent.mkdir(parents=True,exist_ok=True);staging=output.with_suffix('.tmp');staging.write_text(json.dumps(payload,indent=2)+'\n');staging.replace(output)
    (ROOT/'data/enrollment_latest.csv').write_text(stream.getvalue())
    print(f'Verified all five counties, registration date {as_of}; reconciled all party counts and active/inactive totals')
    print(next(row for row in rows if row['borough']=='Staten Island'))


if __name__=='__main__':main()
