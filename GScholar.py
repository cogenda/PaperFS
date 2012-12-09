import cookielib, urllib2, sqlite3, os, tempfile, shutil, re, random, time
from BeautifulSoup import BeautifulSoup
import StringIO

class Article():
    """
    A class representing articles listed on Google Scholar.  The class
    provides basic dictionary-like behavior.
    """
    def __init__(self):
        self.attrs = {'title':         [None, 'Title',          0],
                      'authors':       [None, 'Authors',        1],
                      'journal':       [None, 'Journal',        2],
                      'url':           [None, 'URL',            3],
                      'num_citations': [0,    'Citations',      4],
                      'num_versions':  [0,    'Versions',       5],
                      'url_citations': [None, 'Citations list', 6],
                      'url_versions':  [None, 'Versions list',  7],
                      'url_bibtex':    [None, 'BibTeX',         8],
                      'year':          [None, 'Year',           9]}

    def __getitem__(self, key):
        if key in self.attrs:
            return self.attrs[key][0]
        return None

    def __setitem__(self, key, item):
        if key in self.attrs:
            self.attrs[key][0] = item
        else:
            self.attrs[key] = [item, key, len(self.attrs)]

    def __delitem__(self, key):
        if key in self.attrs:
            del self.attrs[key]

    def as_txt(self):
        # Get items sorted in specified order:
        items = sorted(self.attrs.values(), key=lambda item: item[2])
        # Find largest label length:
        max_label_len = max([len(str(item[1])) for item in items])
        fmt = '%%%ds %%s' % max_label_len
        return '\n'.join([fmt % (item[1], item[0]) for item in items])

    def as_csv(self, header=False, sep='|'):
        # Get keys sorted in specified order:
        keys = [pair[0] for pair in \
                    sorted([(key, val[2]) for key, val in self.attrs.items()],
                           key=lambda pair: pair[1])]
        res = []
        if header:
            res.append(sep.join(keys))
        res.append(sep.join([unicode(self.attrs[key][0]) for key in keys]))
        return '\n'.join(res)

class ChromeCookie(cookielib.CookieJar):
    def __init__(self, host_keys=['.google.com'], policy=None):
        cookielib.CookieJar.__init__(self, policy)
        self._readSqlDB(host_keys)

    def _readSqlDB(self, host_keys):
        cols = ['host_key', 'name', 'value', 'path', 'expires_utc', 'secure', 'persistent']
        sqlcmd = 'select %s from cookies where host_key=:host' % (','.join(cols))

        dbpath = os.path.join(os.getenv('HOME'),
                              '.config', 'google-chrome', 'Default', 'Cookies'
                             )

        tfdb = tempfile.mktemp()
        shutil.copy2(dbpath, tfdb)
        conn = sqlite3.connect(tfdb)
        cursor = conn.cursor()

        rows = []
        for host in host_keys:
            cursor.execute(sqlcmd, {'host': host})
            for r in cursor: rows.append(dict(zip(cols, r)))
        conn.close()
        os.unlink(tfdb)

        for r in rows:
            ck = cookielib.Cookie(version=0,
                                  name              = r['name'],
                                  value             = r['value'],
                                  port              = None,
                                  port_specified    = False,
                                  domain            = r['host_key'],
                                  domain_specified  = False,
                                  domain_initial_dot= True,
                                  path              = r['path'],
                                  path_specified    = True,
                                  secure            = bool(r['secure']),
                                  expires           = r['expires_utc'],
                                  discard           = not bool(r['persistent']),
                                  comment           = None,
                                  comment_url       = None,
                                  rest              = {'HttpOnly': None},
                                  rfc2109           = False)
            self.set_cookie(ck)

class Browser(object):
    UA = 'Mozilla/5.0 (X11; U; FreeBSD i386; en-US; rv:1.9.2.9) Gecko/20100913 Firefox/3.6.9'

    def __init__(self):
        cookieJar =  ChromeCookie(host_keys=['.google.com', '.scholar.google.com'])
        cookies = urllib2.HTTPCookieProcessor(cookieJar)

        self.opener = urllib2.build_opener(cookies)
        self.timeout = 5

    def request(self, req):
        if not isinstance(req, urllib2.Request):
            raise TypeError
        req.add_header('User-Agent', self.UA)

        hdl = self.opener.open(req, timeout=self.timeout)
        return hdl

class Query(object):
    class DefaultParser(object):
        def __init__(self):
            pass
        def parse(self, hdl):
            return hdl.read()

    Parser = DefaultParser

    def __init__(self, browser, url='http://www.googel.com'):
        self.url = url
        self.data = None
        self.headers = {}

        self.browser = browser
        self.parser  = self.Parser()

    def request(self):
        req = urllib2.Request(self.url, self.data, self.headers)
        hdl = self.browser.request(req)
        return self.parser.parse(hdl)

class SearchQuery(Query):
    SCHOLAR_URL = 'http://scholar.google.com/scholar?hl=en&q=%(query)s+author:%(author)s&btnG=Search&as_subj=eng&as_sdt=1,5&as_ylo=&as_vis=0'
    NOAUTH_URL = 'http://scholar.google.com/scholar?hl=en&q=%(query)s&btnG=Search&as_subj=eng&as_std=1,5&as_ylo=&as_vis=0'


    class SearchParser(Query.DefaultParser):
        def __init__(self):
            super(SearchQuery.SearchParser, self).__init__()
            self.site = 'http://scholar.google.com'
            self.soup = None

            self.year_re = re.compile(r'\b(?:20|19)\d{2}\b')
            self.author_end_re = re.compile(' -')

        def parse(self, hdl):
            self.soup = BeautifulSoup(hdl.read())

            article_div = lambda tag: tag.name=='div' and tag.get('class')=='gs_r'

            articles = []
            for div in self.soup.findAll(article_div):
                articles.append( self._parse_article(div) )

            return articles

        def _parse_article(self, div):
            def _as_int(obj):
                try:
                    return int(obj)
                except ValueError:
                    return None

            def _path2url(path):
                if path.startswith('http://'):
                    return path
                if not path.startswith('/'):
                    path = '/' + path
                return self.site + path

            def _parse_links(span):
                for tag in span:
                    if not hasattr(tag, 'name'):
                        continue
                    if tag.name != 'a' or tag.get('href') == None:
                        continue

                    if tag.get('href').startswith('/scholar?cites'):
                        if hasattr(tag, 'string') and tag.string.startswith('Cited by'):
                            article['num_citations'] = \
                                _as_int(tag.string.split()[-1])
                        article['url_citations'] = _path2url(tag.get('href'))

                    if tag.get('href').startswith('/scholar?cluster'):
                        if hasattr(tag, 'string') and tag.string.startswith('All '):
                            article['num_versions'] = \
                                _as_int(tag.string.split()[1])
                        article['url_versions'] = _path2url(tag.get('href'))

                    if tag.get('href').startswith('/scholar.bib?'):
                        if hasattr(tag, 'string') and tag.string.endswith('BibTeX'):
                            article['url_bibtex'] = _path2url(tag.get('href'))
            article = Article()

            for tag in div:
                if not hasattr(tag, 'name'):
                    continue

                if tag.name == 'div' and tag.get('class') == 'gs_ri':
                    if tag.a:
                        article['title'] = ''.join(tag.a.findAll(text=True))
                        article['url'] = _path2url(tag.a['href'])

                    if tag.find('div', {'class': 'gs_a'}):
                        atxt = tag.find('div', {'class': 'gs_a'}).text
                        parts = self.author_end_re.split(atxt)
                        authors = parts[0]
                        article['authors'] = authors.replace(u'&hellip;', '')
                        if len(parts)>1:
                            journal = parts[1]
                            article['journal'] = journal.replace(u'&hellip;', '')

                        year = self.year_re.findall(atxt)
                        article['year'] = year[0] if len(year) > 0 else None

                    if tag.find('div', {'class': 'gs_fl'}):
                        _parse_links(tag.find('div', {'class': 'gs_fl'}))

            return article

    Parser = SearchParser

    def __init__(self, browser, search, author=''):
        params = {'query': urllib2.quote(search.encode('utf-8')),
                  'author': urllib2.quote(author.encode('utf-8'))
                 }
        if len(author)>0:
            url = self.SCHOLAR_URL % params
        else:
            url = self.NOAUTH_URL  % params

        super(SearchQuery, self).__init__(browser, url)

if __name__=='__main__':
    browser = Browser()
    q = SearchQuery(browser, 'Characterization and physical origin of fast Vth transient in NBTI of pMOSFETs with SiON dielectric')

    articles = q.request()
    for art in articles:
        time.sleep(random.randint(1,4))
        if art['url_bibtex']:
            q = Query(browser, art['url_bibtex'])
            print q.request()
        else:
            print art.as_txt()


