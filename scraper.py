import re
import json
import sqlite3

import requests
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import quote

# Common browser headers
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1'
}

SERIES_MAPPING = {
    "Class": "Class (CL)",
    "Counter-Measures": "Counter Measures (CM)",
    "Cyberman": "Cyberman (CY)",
    "Doctor Who - The Monthly Adventures": "D0. Dr Who - Main Range (MR)",
    "Doctor Who - The First Doctor Adventures": "D1. The First Doctor Adventures (1DA)",
    "Doctor Who - The Tenth Doctor Adventures": "D10. The Tenth Doctor Adventures (10DA)",
    "Doctor Who - The Second Doctor Adventures": "D2. The Second Doctor Adventures (2DA)",
    "Doctor Who - The Third Doctor Adventures": "D3. The Third Doctor Adventures (3DA)",
    "Doctor Who - The Fourth Doctor Adventures": "D4. The Fourth Doctor Adventures (4DA)",
    "Doctor Who - The Fifth Doctor Adventures": "D5. The Fifth Doctor Adventures (5DA)",
    "Doctor Who - The Sixth Doctor Adventures": "D6. The Sixth Doctor Adventures (6DA)",
    "Doctor Who - The Seventh Doctor Adventures": "D7. The Seventh Doctor Adventures (7DA)",
    "Doctor Who - The Eighth Doctor Adventures": "D8. The Eighth Doctor Adventures (8DA)",
    "Doctor Who - The Ninth Doctor Adventures": "D9. The Ninth Doctor Adventures (9DA)",
    "Dalek Empire": "Dalek Empire (DE)",
    "Dark Gallifrey (DG)": "Dark Gallifrey (DG)",
    "Doctor Who - Destiny of the Doctor": "Destiny of the Doctor",
    "Doom's Day": "Doom's Day (DD)",
    "Bernice Summerfield": "F1. Bernice Summerfield (BS)",
    "Bernice Summerfield - Books & Audiobooks": "F2. Bernice Summerfield Audiobooks (BSAB)",
    "Doctor Who - The New Adventures of Bernice Summerfield": "F3. The New Adventures of Bernice Summerfield (NABS)",
    "Gallifrey": "Gallifrey (GAL)",
    "I, Davros": "I, DAVROS",
    "Jago & Litefoot": "Jago & Litefoot (J&L)",
    "Missy": "Missy (MIS)",
    "Doctor Who - Once and Future": "Once and Future (O&F)",
    "Doctor Who - Philip Hinchcliffe Presents": "Philip Hincliffe Presents (PHP)",
    "Doctor Who - Short Trips Rarities": "Rarities & Subcriber Short Trips (SST)",
    "Rose Tyler": "Rose Tyler The Dimension Cannon (RT)",
    "Sarah Jane Smith": "Sarah Jane Smith (SJS)",
    "Doctor Who - Short Trips": "Short Trips (ST)",
    "Doctor Who - Short Trips Rarities": "Short Trips Rarities",
    "The Worlds of Doctor Who - Special Releases": "Special Releases (SP)",
    "Torchwood - Monthly Range": "T0. Torchwood Main Range (TMR)",
    "Torchwood - Special Releases": "T1. Torchwood - Specials (TWsp)",
    "Torchwood One": "T2. Torchwood One (TW1)",
    "Torchwood - The Story Continues": "T3. Torchwood - The Story Continues",
    "Torchwood Soho": "T4. Torchwood Soho (TWS)",
    "Doctor Who - The Audio Novels": "The Audio Novels",
    "Doctor Who - The Companion Chronicles": "The Companion Chronicles (CC)",
    "River Song": "The Diary of River Song (RS)",
    "Doctor Who - The Doctor Chronicles": "The Doctor Chronicles (TDC)",
    "Doctor Who - The Early Adventures": "The Early Adventures (EA)",
    "The Lives of Captain Jack": "The Lives of Captain Jack (LCJ)",
    "Doctor Who - The Lost Stories": "The Lost Stories (LS)",
    "The Paternoster Gang": "The Paternoster Gang (PAT)",
    "The Robots": "The Robots (ROB)",
    "Doctor Who - The Stageplays": "The Stageplays (STG)",
    "Doctor Who - The War Doctor": "The War Doctor (WD)",
    "The War Master": "The War Master (WM)",
    "Doctor Who - Time Lord Victorious": "Time Lord Victorious (TLV)",
    "UNIT": "UNIT (UNIT)",
    "UNIT - The New Series": "UNIT - The New Series (UNITNS)",
    "Iris Wildthyme": "F4. Iris Wildthyme (IW)",
    "Iris Wildthyme and Friends":"F5. Iris Wildthyme & Friends (IWF)",
    "Graceless": "F6. Graceless",
    "Doctor Who - Unbound": "Unbound (UN)",
    "Vienna": "F7. Vienna",
    "Charlotte Pollard": "F8. Charlotte Pollard",
    "Doctor Who - The Fugitive Doctor": "The Fugitive Doctor Adventures (FDA)",
    "Call Me Master": "Call Me Master (CMM)",
    "Susan's War": "Susan's War (SW)",
    "V UK": "V - UK",
    # Add other series transformations as needed
}


def infer_series_from_strings(name: str | None, slug: str | None):
    """Infer series using SERIES_MAPPING keys against name or slug heuristically."""
    candidates = []
    if isinstance(name, str):
        candidates.append(name.lower())
    if isinstance(slug, str):
        candidates.append(slug.lower())

    # Exact or token match against mapping keys (conservative)
    for key, mapped in SERIES_MAPPING.items():
        kl = key.lower()
        for cand in candidates:
            if kl == cand or cand.startswith(kl) or kl in cand:
                return mapped

    # Avoid guessing unless clear
    return None

class Database:
    def __init__(self, db_name='bigfinish.db'):
        self.db_name = db_name
        self.conn = None
        self.cursor = None

    def connect(self):
        self.conn = sqlite3.connect(self.db_name)
        self.cursor = self.conn.cursor()

    def close(self):
        if self.conn:
            self.conn.close()

    def create_tables(self):
        self.connect()
        # Create main content table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS content (
                url TEXT PRIMARY KEY,
                title TEXT,
                series TEXT,
                media_type TEXT,
                release_date TEXT,
                about TEXT,
                background TEXT,
                production TEXT,
                duration TEXT,
                isbn TEXT,
                cover_url TEXT,
                written_by TEXT,
                narrated_by TEXT,
                characters TEXT,
                series_tag TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create URLs table with status
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS urls (
                url TEXT PRIMARY KEY,
                visited BOOLEAN DEFAULT FALSE,
                visited_at TIMESTAMP,
                discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Cache for releases known to 404 to avoid repeated fetch attempts
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS missing_releases (
                url TEXT PRIMARY KEY,
                reason TEXT,
                marked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()
        self.close()

    def add_url(self, url):
        """Add a new URL to the database if it doesn't exist"""
        self.connect()
        self.cursor.execute('''
            INSERT OR IGNORE INTO urls (url, discovered_at)
            VALUES (?, CURRENT_TIMESTAMP)
        ''', (url,))
        self.conn.commit()
        self.close()

    def mark_url_visited(self, url):
        """Mark a URL as visited"""
        self.connect()
        self.cursor.execute('''
            INSERT OR REPLACE INTO urls (url, visited, visited_at)
            VALUES (?, TRUE, CURRENT_TIMESTAMP)
        ''', (url,))
        self.conn.commit()
        self.close()

    def get_all_urls(self):
        """Get all URLs and their visited status"""
        self.connect()
        self.cursor.execute('SELECT url, visited FROM urls')
        urls = {row[0]: bool(row[1]) for row in self.cursor.fetchall()}
        self.close()
        return urls

    def save_content(self, data):
        self.connect()
        self.cursor.execute('''
            INSERT OR REPLACE INTO content 
            (url, title, series, release_date, about, background, 
             production, duration, isbn, written_by, narrated_by, characters, cover_url, series_tag, media_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['url'],
            data['title'],
            data['series'],
            data['release_date'],
            data['about'],
            data['background'],
            data['production'],
            data['duration'],
            data['isbn'],
            data['written_by'],
            data['narrated_by'],
            data['characters'],
            data['cover_url'],
            data['series_tag']
            , data.get('media_type')
        ))
        self.conn.commit()
        self.close()

    def return_data_for_url(self, url):
        try:
            self.connect()
            self.cursor.execute('''
                SELECT * FROM content WHERE url = ?
            ''', (url,))

            columns = [description[0] for description in self.cursor.description]
            row = self.cursor.fetchone()

            if row:
                data = dict(zip(columns, row))
                self.close()
                return data

            self.close()
            return None
        except Exception as e:
            print(f"Error fetching data for URL {url}: {e}")
            if hasattr(self, 'close'):
                self.close()
            return None

    def mark_missing_release(self, url, reason=None):
        try:
            self.connect()
            self.cursor.execute('INSERT OR REPLACE INTO missing_releases (url, reason, marked_at) VALUES (?, ?, CURRENT_TIMESTAMP)', (url, reason))
            self.conn.commit()
            self.close()
        except Exception:
            try:
                self.close()
            except Exception:
                pass

    def is_missing_release(self, url):
        try:
            self.connect()
            self.cursor.execute('SELECT url FROM missing_releases WHERE url = ?', (url,))
            r = self.cursor.fetchone()
            self.close()
            return bool(r)
        except Exception:
            try:
                self.close()
            except Exception:
                pass
            return False


class DateParser:
    MONTHS = {
        'january': 1, 'february': 2, 'march': 3, 'april': 4,
        'may': 5, 'june': 6, 'july': 7, 'august': 8,
        'september': 9, 'october': 10, 'november': 11, 'december': 12
    }

    @staticmethod
    def parse_release_date(date_text):
        """
        Parse dates in format "Released Month YYYY" to "YYYY-MM-DD"
        Example: "Released March 2020" -> "2020-03-01"
        """
        if not date_text:
            return None

        # Clean up the input text
        date_text = date_text.lower().strip()
        if date_text.startswith('released '):
            date_text = date_text[9:].strip()

        # Extract month and year using regex
        pattern = r'([a-zA-Z]+)\s+(\d{4})'
        match = re.search(pattern, date_text)

        if not match:
            return None

        month_str, year_str = match.groups()
        month_str = month_str.lower()

        # Get month number
        if month_str not in DateParser.MONTHS:
            return None

        month_num = DateParser.MONTHS[month_str]

        # Create datetime object
        try:
            date_obj = datetime(int(year_str), month_num, 1)
            return date_obj.strftime('%Y-%m-%d')
        except ValueError:
            return None

    @staticmethod
    def extract_embedded_release_data(html):
        """Extract JSON object assigned to `releaseData` in inline scripts."""
        try:
            # Look for patterns like `releaseData = { ... };` or `var releaseData = { ... };`
            m = re.search(r'releaseData\s*=\s*(\{.*?\})\s*;', html, re.DOTALL)
            if not m:
                m = re.search(r'var\s+releaseData\s*=\s*(\{.*?\})\s*;', html, re.DOTALL)
            if m:
                json_text = m.group(1)
                # Remove trailing commas which break JSON
                json_text = re.sub(r',\s*}', '}', json_text)
                json_text = re.sub(r',\s*\]', ']', json_text)
                return json.loads(json_text)

            # Try multiple approaches: search for the token and then balanced-brace parse
            # Also try a lightly unescaped version where common backslash-escapes are removed
            unescaped = html.replace('\\"', '"')
            for token in ['"releaseData"', 'releaseData', "'releaseData'"]:
                idx = unescaped.find(token)
                if idx == -1:
                    continue
                # find the first '{' after the token
                brace_pos = unescaped.find('{', idx)
                if brace_pos == -1:
                    continue

                depth = 0
                i = brace_pos
                in_string = False
                escape = False
                while i < len(unescaped):
                    ch = unescaped[i]
                    if in_string:
                        if escape:
                            escape = False
                        elif ch == '\\':
                            escape = True
                        elif ch == '"':
                            in_string = False
                    else:
                        if ch == '"':
                            in_string = True
                        elif ch == '{':
                            depth += 1
                        elif ch == '}':
                            depth -= 1
                            if depth == 0:
                                json_text = unescaped[brace_pos:i+1]
                                # Clean trailing commas
                                json_text = re.sub(r',\s*}', '}', json_text)
                                json_text = re.sub(r',\s*\]', ']', json_text)
                                try:
                                    return json.loads(json_text)
                                except Exception:
                                    try:
                                        unescaped2 = json_text.encode('utf-8').decode('unicode_escape')
                                        return json.loads(unescaped2)
                                    except Exception:
                                        break
                    i += 1

            return None
        except Exception:
            return None


class Scraper:
    def __init__(self, base_url):
        self.base_url = base_url
        self.db = Database()
        self.db.create_tables()
        self.all_links = self.db.get_all_urls()  # Load all URLs from database
        self.date_parser = DateParser()

    def get_html(self, url):
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            print(f'Error fetching {url}: {e}')
            return None

    def get_all_links(self, html, only_releases=False):
        try:
            soup = BeautifulSoup(html, 'html.parser')
        except Exception as e:
            print(f"Error parsing HTML: {e}")
            return []
        links = soup.find_all('a')

        allowed_parts = ['/releases/', '/ranges/', '/hubs/'] if not only_releases else ['/releases/', '/ranges/']
        disallowed_parts = ['facebook.com', 'twitter', 'youtube', '/basket/', '/pages/v/']
        must_contain = ['bigfinish.com']
        parsed_links = []

        for link in links:
            href = link.get('href')
            if href and any(part in href for part in allowed_parts) and not any(
                    part in href for part in disallowed_parts):
                full_url = href if href.startswith('http') else self.base_url + href
                if all(part in full_url for part in must_contain):
                    if full_url not in self.all_links:
                        self.all_links[full_url] = False
                        self.db.add_url(full_url)  # Add new URL to database
                    parsed_links.append(full_url)

        return parsed_links

    def clean_title(self, title):
        if title:
            # Match pattern: <1-6 chars><dot><space><rest>
            match = re.match(r'^([^\s]{1,6})\.\s+(.+)$', title)
            if match:
                prefix = match.group(1)  # The prefix before the dot
                rest = match.group(2)  # Everything after dot and space
                return prefix, rest
        return None, title

    def parse_data(self, url, html):
        try:
            soup = BeautifulSoup(html, 'html.parser')
        except Exception as e:
            print(f"Error parsing {url}: {e}")
            return None
        data = {
            'url': url,
            'title': None,
            'series': None,
            'media_type': None,
            'release_date': None,
            'about': None,
            'background': None,
            'production': None,
            'duration': None,
            'isbn': None,
            'written_by': None,
            'narrated_by': None,
            'characters': None,
            'cover_url': None,
            'series_tag': None
        }
        # Prefer embedded JSON data when available (client-side rendered pages)
        embedded = DateParser.extract_embedded_release_data(html)
        if embedded:
            print("ABOUT FIELD:", repr(embedded.get('about')))
            print("DESCRIPTION FIELD:", repr(embedded.get('description')))
        if embedded:
            # Map commonly available fields from the embedded object with robust fallbacks
            try:
                # Title
                title = embedded.get('title') or embedded.get('name') or embedded.get('release_title')
                if title:
                    data['title'] = title.strip()

                # Series / range
                series = (embedded.get('range') or embedded.get('series_name') or embedded.get('series') or
                          (embedded.get('meta') or {}).get('series'))
                if series:
                    # If nested object
                    if isinstance(series, dict):
                        series_name = series.get('name') or series.get('title')
                        data['series'] = SERIES_MAPPING.get(series_name, series_name) if series_name else None
                    else:
                        data['series'] = SERIES_MAPPING.get(series, series)

                # Series tag / slug
                series_tag = embedded.get('release_slug') or embedded.get('slug') or (embedded.get('meta') or {}).get('slug')
                if series_tag:
                    data['series_tag'] = series_tag

                # Release date
                rdate = embedded.get('release_date') or embedded.get('released') or (embedded.get('meta') or {}).get('release_date')
                if rdate:
                    if isinstance(rdate, str) and re.match(r"\d{4}-\d{2}-\d{2}", rdate):
                        data['release_date'] = rdate
                    else:
                        parsed = DateParser.parse_release_date(str(rdate))
                        if parsed:
                            data['release_date'] = parsed

                # About / description
                about = embedded.get('about')
                
                if isinstance(about, str):
                    data['about'] = about
                
                elif isinstance(about, dict):
                    summary = about.get('summary')
                
                    # Ignore obvious prices
                    if (
                        isinstance(summary, str)
                        and len(summary) > 50
                        and not summary.startswith('$')
                    ):
                        data['about'] = summary
                
                if not data['about']:
                    description = embedded.get('description')
                
                    if isinstance(description, str) and len(description) > 50:
                        data['about'] = description
                
                if not data['about']:
                    meta_desc = (embedded.get('meta') or {}).get('description')
                
                    if isinstance(meta_desc, str) and len(meta_desc) > 50:
                        data['about'] = meta_desc

                # Writers / authors
                writers = embedded.get('writers') or embedded.get('written_by') or (embedded.get('credits') or {}).get('writers')
                if writers:
                    if isinstance(writers, list):
                        names = []
                        for w in writers:
                            if isinstance(w, dict):
                                names.append(w.get('name') or w.get('full_name') or '')
                            else:
                                names.append(str(w))
                        data['written_by'] = ', '.join([n for n in names if n])
                    else:
                        data['written_by'] = str(writers)

                # Image / cover
                img = embedded.get('image') or embedded.get('cover') or embedded.get('cover_url') or (embedded.get('meta') or {}).get('image')
                if img:
                    img_url = img.get('url') if isinstance(img, dict) else img
                    if img_url:
                        data['cover_url'] = img_url if img_url.startswith('http') else self.base_url + img_url

                # Determine media type from variants
                variants = embedded.get('variants') or embedded.get('products') or embedded.get('variants_list')
                if isinstance(variants, list):
                    types = [v.get('type') for v in variants if isinstance(v, dict) and v.get('type')]
                    types = [t.lower() for t in types if isinstance(t, str)]
                    # magazine types contain 'mag'
                    if any('mag' in t for t in types):
                        data['media_type'] = 'magazine'
                    # audio/book types may contain 'book' or 'audio' or 'abridged'
                    elif any(
                        any(sub in media_type for sub in ('book', 'audio', 'abridg', 'novel'))
                        for media_type in types
                    ):
                        data['media_type'] = 'book'
                    elif types:
                        data['media_type'] = types[0]

                # Technical details: duration and ISBN
                tech = embedded.get('technical_details') or embedded.get('technical') or embedded.get('meta')
                if tech and isinstance(tech, dict):
                    dur = tech.get('duration') or tech.get('length')
                    if dur:
                        # dur may be "120" or "120 mins" or "2 hours"
                        m = re.search(r"(\d{1,4})", str(dur))
                        if m:
                            data['duration'] = m.group(1)
                    isbn = tech.get('isbn') or tech.get('Digital Retail ISBN') or tech.get('digital_isbn')
                    if isbn:
                        data['isbn'] = str(isbn)

                # Cast / contributors
                cast = embedded.get('cast') or embedded.get('contributors') or (embedded.get('credits') or {}).get('cast')
                if cast and isinstance(cast, list):
                    narrators = []
                    characters = []
                    for c in cast:
                        # contributor dicts often include 'person'/'name' and 'role'/'character'
                        if isinstance(c, dict):
                            name = c.get('name') or c.get('person') or c.get('actor') or c.get('full_name')
                            # role field may be 'role', 'character', 'as', or nested
                            role = c.get('role') or c.get('character') or c.get('as') or c.get('role_name')
                            # Some structures include an array of roles under 'roles' or 'characters'
                            if not role and 'roles' in c and isinstance(c.get('roles'), list):
                                role = ', '.join([r.get('name') if isinstance(r, dict) else str(r) for r in c.get('roles')])
                            if name:
                                narrators.append(name)
                            if role:
                                if isinstance(role, list):
                                    characters.extend([str(r) for r in role])
                                elif isinstance(role, dict):
                                    characters.append(role.get('name') or str(role))
                                else:
                                    characters.extend([rc.strip() for rc in str(role).replace('/', ',').split(',') if rc.strip()])
                        else:
                            narrators.append(str(c))
                    if narrators:
                        data['narrated_by'] = ', '.join(sorted(set([n for n in narrators if n])))
                    if characters:
                        data['characters'] = ', '.join(sorted(set([c for c in characters if c])))

                # If writers still missing, look in contributors for role=Writer/Author
                if not data.get('written_by'):
                    contribs = embedded.get('contributors') or (embedded.get('credits') or {}).get('contributors')
                    writers_list = []
                    if isinstance(contribs, list):
                        for c in contribs:
                            if isinstance(c, dict):
                                role = (c.get('role') or c.get('contribution') or '').lower()
                                name = c.get('name') or c.get('person') or c.get('full_name')
                                if 'writer' in role or 'author' in role or 'written' in role:
                                    if name:
                                        writers_list.append(name)
                    if writers_list:
                        data['written_by'] = ', '.join(sorted(set(writers_list)))

                # Production credits may contain technical details like duration and ISBN
                prod = embedded.get('production_credits') or embedded.get('production') or embedded.get('productionCredits')
                tech = None
                if isinstance(prod, dict):
                    tech = prod.get('technical_details') or prod.get('technicalDetails') or prod.get('technical')
                elif isinstance(prod, list):
                    for p in prod:
                        if isinstance(p, dict):
                            tech = p.get('technical_details') or p.get('technical') or tech
                            if tech:
                                break

                # If technical details found, extract duration and ISBN by key-matching
                if tech:
                    # tech may be dict or list
                    def find_in_tech(obj, key_sub):
                        if not obj:
                            return None
                        if isinstance(obj, dict):
                            for k, v in obj.items():
                                if key_sub in k.lower():
                                    return v
                                # nested
                                if isinstance(v, (dict, list)):
                                    found = find_in_tech(v, key_sub)
                                    if found:
                                        return found
                        elif isinstance(obj, list):
                            for item in obj:
                                found = find_in_tech(item, key_sub)
                                if found:
                                    return found
                        return None

                    dur_val = find_in_tech(tech, 'duration') or find_in_tech(tech, 'length') or find_in_tech(tech, 'minutes')
                    if dur_val:
                        m = re.search(r"(\d{1,5})", str(dur_val))
                        if m:
                            data['duration'] = m.group(1)

                    isbn_val = find_in_tech(tech, 'isbn') or find_in_tech(tech, 'digital_isbn') or find_in_tech(tech, 'retail_isbn')
                    if isbn_val:
                        data['isbn'] = str(isbn_val)
                # If ISBN still not found, search the whole HTML for an ISBN pattern
                if not data.get('isbn'):
                    try:
                        # Common ISBN patterns (10 or 13 digits, possibly with hyphens)
                        m = re.search(r'ISBN(?:-13)?:?\s*([0-9\-\sXx]{10,17})', html)
                        if m:
                            candidate = re.sub(r'\s+', '', m.group(1)).strip()
                            data['isbn'] = candidate
                    except Exception:
                        pass
            except Exception as e:
                print(f"Error mapping embedded JSON for {url}: {e}")

        product_desc = soup.find('div', {'class': 'product-desc'})
        if product_desc:
            data['title'] = product_desc.find('h3').text.strip() if product_desc.find('h3') else None
            prefix, rest = self.clean_title(data['title'])
            if prefix:
                data['series_tag'] = prefix
                data['title'] = rest

                prefix, rest = self.clean_title(data['title'])
                if prefix:
                    data['series_tag'] = data['series_tag'] + '.' + prefix
                    data['title'] = rest

            data['series'] = product_desc.find('h6').text.strip() if product_desc.find('h6') else None

            # Apply series mapping
            if data['series'] in SERIES_MAPPING:
                data['series'] = SERIES_MAPPING[data['series']]

            if re.search(f"{data['series']}:\\s", data['title'], re.IGNORECASE):
                data['title'] = re.sub(f"{data['series']}:\\s", '', data['title'], flags=re.IGNORECASE)
            # Try replacing " -" with :
            tmp_series = data['series'].replace(" -", ":")
            if re.search(f"{tmp_series}:\\s", data['title'], re.IGNORECASE):
                data['title'] = re.sub(f"{tmp_series}:\\s", '', data['title'], flags=re.IGNORECASE)

        cover_div = soup.find('div', {'class': 'detail-page-image'})
        if cover_div:
            cover_img = cover_div.find('img')
            if cover_img:
                data['cover_url'] = cover_img.get('src')
                if data['cover_url'] and not data['cover_url'].startswith('http'):
                    data['cover_url'] = self.base_url + data['cover_url']
                data['title'] = cover_img.get('alt') if cover_img.get('alt') else data['title']

        # Parse release date
        release_date_div = soup.find('div', {'class': 'release-date'})
        if release_date_div:
            date_text = release_date_div.text.strip()
            parsed_date = DateParser.parse_release_date(date_text)
            if parsed_date:
                data['release_date'] = parsed_date

        # Parse writers and narrators
        #paragraphs = product_desc.find_all('p') if product_desc else []
        #if len(paragraphs) > 0:
        #    data['written_by'] = ', '.join([a.text.strip() for a in paragraphs[0].find_all('a')])
        #if len(paragraphs) > 1:
        #    data['narrated_by'] = ', '.join([a.text.strip() for a in paragraphs[1].find_all('a')])
# Parse contributors from new Big Finish page layout

        for p in soup.find_all("p"):
        
            label = p.find(
                "span",
                class_=lambda c: c and "font-medium" in str(c)
            )
        
            if not label:
                continue
            
            field_name = label.get_text(strip=True).rstrip(":")
        
            values = [
                a.get_text(strip=True)
                for a in p.find_all("a")
            ]
        
            if not values:
                continue
            
            if field_name == "Written By":
                data["written_by"] = ", ".join(values)
        
            elif field_name == "Starring":
                data["narrated_by"] = ", ".join(values)


        # Parse tabs content
        for tab_id in ['tab1', 'tab2', 'tab5', 'tab6']:
            tab = soup.find('div', {'id': tab_id})
            if tab:
                if tab_id == 'tab1':
                    text = tab.get_text("\n", strip=True)

                    if text and len(text) > len(data.get('about') or ''):
                        data['about'] = text  # Preserves HTML formatting
                    elif tab_id == 'tab2':
                        data['background'] = str(tab)  # Preserves HTML formatting
                    elif tab_id == 'tab5':
                        # Extract narrators and their characters  
                        narrators = []
                        characters = []

                    # Find all elements with narrator info
                    for element in tab.stripped_strings:
                        # If element contains parentheses, it's likely a character
                        if '(' in element and ')' in element:
                            # Extract character name from between parentheses
                            char = re.search(r'\((.*?)\)', element)
                            if char:
                                # Replace forward slashes with commas first
                                char_string = char.group(1).replace('/', ',')
                                # Split by comma and clean
                                char_parts = [c.strip() for c in char_string.split(',')]
                                # Add cleaned character names
                                characters.extend([c for c in char_parts if c])
                            
                            # Handle narrator part
                            narrator = element.split('(')[0].strip()
                            if narrator:
                                narrator_parts = [n.strip() for n in narrator.replace('/', ',').split(',')]
                                narrators.extend(narrator_parts)
                        elif element:
                            narrator_parts = [n.strip() for n in element.replace('/', ',').split(',')]
                            narrators.extend(narrator_parts)

                    # Join the unique narrators and characters with proper formatting
                    data['narrated_by'] = ', '.join(sorted(set(filter(None, narrators))))
                    data['characters'] = ', '.join(sorted(set(filter(None, characters))))
                elif tab_id == 'tab6':
                    content = tab.text.strip()  # Production info doesn't need HTML
                    data['production'] = content
                    # Extract duration and ISBN
                    if 'Duration:' in content:
                        data['duration'] = content.split('Duration: ')[1].split(' ')[0].split('\n')[0]
                    if 'Digital Retail ISBN: ' in content:
                        data['isbn'] = content.split('Digital Retail ISBN: ')[1].split(' ')[0].split('\n')[0]
                        # Check if ISBN is valid
                        if not re.match(r'\d{3}-\d{1,5}-\d{1,7}-\d{1}', data['isbn']):
                            data['isbn'] = None
                    elif 'Physical Retail ISBN: ' in content:
                        data['isbn'] = content.split('Physical Retail ISBN: ')[1].split(' ')[0].split('\n')[0]
                        # Check if ISBN is valid
                        if not re.match(r'\d{3}-\d{1,5}-\d{1,7}-\d{1}', data['isbn']):
                            data['isbn'] = None

        # If characters still missing, attempt a broad regex scan for 'Name (Character)' patterns in the HTML
        if not data.get('characters'):
            try:
                # find patterns like 'Actor Name (Character Name)' and collect character names
                
                if tab:
                    source_text = tab.get_text(" ", strip=True)
                else:
                    source_text = ""
                
                matches = re.findall(
                    r"[A-Z][A-Za-z\-\. '\u00C0-\u017F]+\s*\(([^)]+)\)",
                    source_text
                )

                chars = []
                for m in matches:
                    # split multi-character lists like 'Alice / Bob' or 'Alice, Bob'
                    parts = re.split(r"/|,|;", m)
                    for p in parts:
                        p = p.strip()
                        if p and len(p) > 1:
                            chars.append(p)
                if chars:
                    data['characters'] = ', '.join(sorted(set(chars)))
            except Exception:
                pass

        # Coerce complex fields to strings before saving to SQLite
        for key in ['about', 'background', 'production']:
            val = data.get(key)
            if isinstance(val, dict):
                # Prefer 'summary' if present
                if 'summary' in val and isinstance(val['summary'], str):
                    data[key] = val['summary']
                else:
                    try:
                        data[key] = json.dumps(val)
                    except Exception:
                        data[key] = str(val)
            elif isinstance(val, list):
                data[key] = ', '.join([str(x) for x in val])


        print("ABOUT:")
        print(repr(data['about']))


        self.db.save_content(data)
        return data

    def run(self):
        if not self.all_links:
            print("No stored URLs found. Starting fresh crawl...")
            html = self.get_html(self.base_url)
            if html:
                self.get_all_links(html)
        else:
            print(f"Loaded {len(self.all_links)} URLs from database")

        while True:
            unvisited_links = [link for link, visited in self.all_links.items()
                               if not visited
                               and "/releases/v/" in link
                               ]

            if not unvisited_links:
                print("No more unvisited links to process")
                break

            print(f"Processing {len(unvisited_links)} unvisited links...")
            for link in unvisited_links:
                print(f'Visiting {link}')
                content = self.get_html(link)
                if content:
                    self.get_all_links(content, True)
                    if "/releases/v/" in link:
                        self.parse_data(link, content)
                    self.db.mark_url_visited(link)
                    self.all_links[link] = True

    def get_statistics(self):
        total_urls = len(self.all_links)
        visited_urls = sum(1 for visited in self.all_links.values() if visited)
        unvisited_urls = total_urls - visited_urls

        print("\nCrawler Statistics:")
        print(f"Total URLs indexed: {total_urls}")
        print(f"Visited URLs: {visited_urls}")
        print(f"Remaining URLs: {unvisited_urls}")


class Search:
    def __init__(self):
        self.base_url = 'https://www.bigfinish.com'

    def search(self, query):
        def normalize_media(mt: str | None):
            if not mt:
                return None
            mt = mt.lower()
            if mt in ('book', 'audio', 'audiobook'):
                return 'book'
            if 'mag' in mt or 'magazine' in mt:
                return 'magazine'
            return mt

        # If caller appended a media token using '||', strip it out and keep for filtering
        media_token = None
        if isinstance(query, str) and '||' in query:
            parts = query.split('||')
            if len(parts) > 1:
                media_token = normalize_media(parts[-1])
                query = '||'.join(parts[:-1])

        # Normalize query for search APIs
        raw_query = query.replace(':', ' ').strip()
        encoded_query = quote(raw_query)

        db = Database()
        # Ensure DB schema exists before any lookups
        try:
            db.create_tables()
        except Exception:
            pass

        datas = []

        # Try the new JSON search API first (POST)
        api_url = f'{self.base_url}/api/search'
        try:
            resp = requests.post(api_url, json={"q": raw_query, "limit": 20, "offset": 0}, headers={**headers, 'Accept': 'application/json'})
            resp.raise_for_status()
            payload = resp.json()
            # expected results in payload['hits'] (list)
            hits = payload.get('hits') if isinstance(payload, dict) else None
            if not hits and isinstance(payload, list):
                hits = payload
            if not hits:
                hits = []
        except requests.exceptions.RequestException as e:
            print(f'POST {api_url} failed: {e} â€” falling back to legacy suggest endpoint')
            # Fallback to legacy suggest endpoint (GET)
            suggest_url = f'{self.base_url}/search_results/suggest/{encoded_query}'
            try:
                resp = requests.get(suggest_url, headers=headers)
                resp.raise_for_status()
                legacy = resp.json()
                # legacy API returned a dict of results keyed by index
                if isinstance(legacy, dict):
                    hits = list(legacy.values())
                elif isinstance(legacy, list):
                    hits = legacy
                else:
                    hits = []
            except requests.exceptions.RequestException as e2:
                print(f'Fallback GET {suggest_url} failed: {e2}')
                return []

        # Normalize hits to a list of result dicts
        if not isinstance(hits, list):
            hits = []

        # If a media token was provided, try to filter hits by any obvious type/format fields
        def result_matches_media(res: dict, token: str) -> bool:
            if not isinstance(res, dict) or not token:
                return True
            token = token.lower()
            keys_to_check = ['type', 'product_type', 'productType', 'format', 'category', 'variant', 'kind', 'label']
            for k in keys_to_check:
                v = res.get(k)
                if isinstance(v, str):
                    lv = v.lower()
                    if token == 'book' and any(sub in lv for sub in ('book', 'audio', 'novel', 'abridg')):
                        return True
                    if token == 'magazine' and 'mag' in lv:
                        return True
                elif isinstance(v, dict):
                    # nested type info
                    t = v.get('type') or v.get('label') or v.get('name')
                    if isinstance(t, str) and token in t.lower():
                        return True

            # Also check for URLs that include 'mag' or 'books'
            maybe_url = res.get('url') or res.get('link')
            if isinstance(maybe_url, str):
                ml = maybe_url.lower()
                if token == 'book' and any(x in ml for x in ('book', '/books/', '/audio/')):
                    return True
                if token == 'magazine' and 'mag' in ml:
                    return True

            # Default: do not match
            return False

        # Note: we defer final media-type filtering until after parsing/synthesizing results

        for result in hits:
            print(json.dumps(result, indent=2))
            # Try common id fields
            if not isinstance(result, dict):
                continue
            release_id = None
            # Prefer numeric id from release_slug (slug often ends with -<id>)
            rs = result.get('release_slug') or result.get('slug') or result.get('name')
            if isinstance(rs, str):
                m = re.search(r'-(\d+)$', rs)
                if m:
                    release_id = m.group(1)
            if not release_id:
                for k in ('product_id', 'productId', 'release_id', 'reference_id', 'id'):
                    if k in result and result.get(k):
                        release_id = result.get(k)
                        break
            if not release_id:
                # some legacy entries may contain an 'url' we can extract an id from
                maybe_url = result.get('url') or result.get('link')
                if maybe_url:
                    m = re.search(r'/releases/v/(\d+)', maybe_url)
                    if m:
                        release_id = m.group(1)
            if not release_id:
                continue

            # Build a sensible URL if possible; many search hits are 'audiobook_models' with rich metadata
            new_url = f'{self.base_url}/releases/{result.get("release_slug")}' if result.get('release_slug') else f'{self.base_url}/releases/v/{release_id}'

            # If this hit is already an audiobook model (search index provides useful metadata),
            # synthesize a result without fetching the page to avoid many 404s.
            index_uid = result.get('indexUid') or result.get('index_uid')
            if index_uid and 'audio' in index_uid.lower():
                # Build a synthesized result from search hit fields (avoid fetching page when possible)
                # Compose a richer description from multiple possible fields
                desc_parts = []
                for k in ('description', 'long_description', 'summary', 'excerpt', 'body', 'details'):
                    v = result.get(k)
                    if isinstance(v, str) and v.strip():
                        desc_parts.append(v.strip())

                synth = {
                    'url': new_url,
                    'title': result.get('name') or result.get('title'),
                    'series': None,
                    'release_date': None,
                    'about': '\n\n'.join(desc_parts) if desc_parts else result.get('description'),
                    'background': None,
                    'production': None,
                    'duration': result.get('duration'),
                    'isbn': None,
                    # Do NOT set `written_by` from contributors (these are performers); set narrators instead
                    'written_by': None,
                    'narrated_by': ', '.join([c.get('name') for c in result.get('contributors')]) if result.get('contributors') else None,
                    'characters': None,
                    'cover_url': (result.get('image') if isinstance(result.get('image'), str) else None),
                    'series_tag': None,
                    'media_type': 'book'
                }
                # Prefer explicit series/range fields from the hit
                for series_key in ('range', 'range_name', 'range_slug', 'series', 'series_name', 'collection'):
                    sv = result.get(series_key)
                    if isinstance(sv, str) and sv.strip():
                        synth['series'] = sv.strip()
                        break
                # fallback: try product metadata
                if not synth['series'] and isinstance(result.get('product'), dict):
                    for series_key in ('range', 'range_name', 'range_slug', 'series', 'series_name', 'collection'):
                        sv = result['product'].get(series_key)
                        if isinstance(sv, str) and sv.strip():
                            synth['series'] = sv.strip()
                            break
                # fallback: try to split name on ':'
                if not synth['series'] and isinstance(result.get('name'), str) and ':' in result.get('name'):
                    synth['series'] = result.get('name').split(':')[0].strip()
                # If characters were provided in the hit, use them; otherwise, optionally use contributors as tags
                if result.get('characters'):
                    if isinstance(result.get('characters'), list):
                        synth['characters'] = ', '.join([str(x) for x in result.get('characters')])
                    else:
                        synth['characters'] = str(result.get('characters'))
                # do not use contributors as a fallback for characters; characters should come from page or explicit field

                # If no explicit series found, try mapping using SERIES_MAPPING heuristics
                if not synth.get('series'):
                    synth['series'] = infer_series_from_strings(result.get('name'), result.get('release_slug'))

                # Try a single page fetch to enrich synthesized data (published year, ISBN, writers)
                try:
                    # Try a couple of URL patterns to find the release page that contains embedded JSON
                    tried = []
                    candidates = []

                    if result.get('release_slug'):
                        candidates.append(
                            f"{self.base_url}/releases/v/{result.get('release_slug')}"
                        )

                        # keep old format as fallback
                        candidates.append(
                            f"{self.base_url}/releases/{result.get('release_slug')}"
                        )

                    if release_id:
                        candidates.append(
                            f"{self.base_url}/releases/v/{release_id}"
                        )

                    for candidate in candidates:
                        if db.is_missing_release(candidate):
                            continue
                        tried.append(candidate)
                        resp = requests.get(candidate, headers=headers)
                        print(f"Trying enrichment URL: {candidate}")
                        print(f"Status: {resp.status_code}")
                        if resp.status_code == 200:
                            parsed = Scraper(self.base_url).parse_data(candidate, resp.text)
                            print(
                                f"Parsed author={parsed.get('written_by')} "
                                f"isbn={parsed.get('isbn')}"
                            )
                            if parsed:
                                for fld in (
                                    'written_by',
                                    'characters',
                                    'release_date',
                                    'isbn',
                                    'series',
                                    'about',
                                    'background'
                                ):
                                    if parsed.get(fld):
                                        synth[fld] = parsed.get(fld)

                                # Special handling for cast
                                search_cast = set()
                                page_cast = set()

                                if synth.get('narrated_by'):
                                    search_cast.update(
                                        x.strip()
                                        for x in synth['narrated_by'].split(',')
                                        if x.strip()
                                    )

                                if parsed.get('narrated_by'):
                                    page_cast.update(
                                        x.strip()
                                        for x in parsed['narrated_by'].split(',')
                                        if x.strip()
                                    )

                                synth['narrated_by'] = ', '.join(
                                    sorted(search_cast | page_cast)
                                )
                                # stop after successful parse
                                break
                        else:
                            if resp.status_code == 404:
                                db.mark_missing_release(candidate, reason='404')
                except requests.exceptions.RequestException:
                    pass

                datas.append(synth)
                continue

            # Check if the new url is already in the database
            data = db.return_data_for_url(new_url)
            # If we have cached data but key fields are missing, re-fetch and re-parse
            if data and data.get('title'):
                datas.append(data)
                continue
            elif data and not data.get('title'):
                try:
                    resp = requests.get(new_url, headers=headers)
                    resp.raise_for_status()
                    text = resp.text
                    parsed = Scraper(self.base_url).parse_data(new_url, text)
                    if parsed:
                        datas.append(parsed)
                        continue
                except requests.exceptions.RequestException:
                    # fall back to using cached incomplete data
                    datas.append(data)
                    continue

            try:
                resp = requests.get(new_url, headers=headers)
                resp.raise_for_status()
                text = resp.text
                parsed = Scraper(self.base_url).parse_data(new_url, text)
                if parsed:
                    datas.append(parsed)
            except requests.exceptions.RequestException as e:
                print(f'Failed fetching release {new_url}: {e}')

        # Enrich top-N parsed results by fetching their release pages to populate missing fields
        try:
            N = 10
            to_enrich = [d for d in datas if (not d.get('release_date') or not d.get('isbn') or not d.get('written_by'))]
            for d in to_enrich[:N]:
                url = d.get('url')
                if not url:
                    continue
                if db.is_missing_release(url):
                    continue
                try:
                    resp = requests.get(url, headers=headers, timeout=8)
                    if resp.status_code == 200:
                        parsed = Scraper(self.base_url).parse_data(url, resp.text)
                        if parsed:
                            for fld in ('written_by', 'narrated_by', 'characters', 'release_date', 'isbn', 'series'):
                                if parsed.get(fld):
                                    d[fld] = parsed.get(fld)
                    else:
                        if resp.status_code == 404:
                            db.mark_missing_release(url, reason='404')
                except requests.exceptions.RequestException:
                    pass
        except Exception:
            pass

        try:
            db.close()
        except Exception:
            pass

        # If media_token was provided, filter parsed results by detected media_type
        if media_token:
            datas = [d for d in datas if normalize_media(d.get('media_type')) == media_token]

        return datas


if __name__ == '__main__':
    Search().search('Doctor Who')


def test():
    scraper = Scraper('https://www.bigfinish.com')
    try:
        scraper.run()
        scraper.get_statistics()
    except KeyboardInterrupt:
        print("\nCrawling interrupted by user")
        scraper.get_statistics()
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        scraper.get_statistics()
 