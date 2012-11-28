import sqlite3, os.path, pickle
import u1db
import DataModel
from Utils import *

basedir = '/home/hash/Documents/Papers'

class SimpleQuery(object):
    col_map = []
    sql_template = None

    def __init__(self, conn, immediate=True, **params):
        self.conn = conn
        self.params = params

        self.cursor = None

        if immediate: self.query()

    def query(self):
        self.cursor = self.conn.cursor()

        cmd = [v for k,v in self.col_map]
        cmd = self.sql_template % u','.join(cmd)
        self.cursor.execute(cmd, self.params)

    def __iter__(self):
        if self.cursor:
            return self
        else:
            raise ValueError

    def next(self):
        row = self.cursor.fetchone()

        if row is None:
            raise StopIteration

        data = dict(zip([k for k,_ in self.col_map], row))
        return data

class QZPaper(SimpleQuery):
    col_map = [
        ('title',       'ztitle'),
        ('year',        'zyear'),
        ('volume',      'zvolume'),
        ('issue',       'zissue'),
        ('pages',       'zpages'),
        ('doi',         'zdoi'),
        ('url',         'zurl'),
        ('path',        'zpath'),
        ('_journal',    'zjournal'),
        ('_id',         'z_pk'),
        ('date_import', 'zimporteddate'),
        ('abstract',    'zabstract'),
    ]
    sql_template = 'select %s from zpaper'

class QZAuthorsOfPaper(SimpleQuery):
    col_map = [
        ('lastname',    'zauthor.zlastname'),
        ('firstname',   'zauthor.zfirstname'),
    ]
    sql_template = '''select %s, pa.zorder from zorderedauthor as pa, zpaper, zauthor
where pa.zpaper=:paper and pa.zpaper=zpaper.z_pk and pa.zauthor=zauthor.z_pk
order by pa.zorder'''

class QZJournalOfPaper(SimpleQuery):
    col_map = [
        ('name',        'zjournal.zname'),
    ]
    sql_template = '''select %s from zpaper, zjournal
where zjournal.z_pk=zpaper.zjournal and zpaper.z_pk=:paper'''


class QGidsOfPaper(SimpleQuery):
    col_map = [
        ('group_id',        'z_3groups'),
    ]
    sql_template = '''select %s from z_3papers
                      where z_3papers.z_11papers2=:paper'''

class QRootGroup(SimpleQuery):
    col_map = [
        ('name',        'zname'),
        ('_id',         'z_pk'),
    ]
    sql_template = '''select %s from zgroup where zparent is null'''

class QChildGroup(SimpleQuery):
    col_map = [
        ('name',        'zname'),
        ('_id',         'z_pk'),
    ]
    sql_template = '''select %s from zgroup where zparent=:parent'''

def importGroups(conn):
    exclude = ['ADS', 'arXiv', 'Citeseer', 'Goole Books', 'Google Scholar',
               'PubMed', 'Web of Science', 'ACM', 'IEEE Xplore', 'MathSciNet',
               'Project Muse', 'New Collection']
    gid2tags = {}

    def cgroup(pname, pid):
        qChildGroup = QChildGroup(conn, parent=pid)
        for cgrp in qChildGroup:
            gid  = cgrp['_id']
            name = cgrp['name']
            if name in exclude: continue

            name = u'%s:%s' % (name, pname)

            gid2tags[gid] = [name]
            gid2tags[gid].extend(gid2tags[pid])

            cgroup(name, gid)


    qRootGroup = QRootGroup(conn)
    for rgrp in qRootGroup:
        gid  = rgrp['_id']
        name = rgrp['name']
        if name in exclude: continue

        gid2tags[gid] = [name]
        cgroup(name, gid)

    return gid2tags

def importPapers(conn, db, grp_tags):
    cnt = 0
    isinstance(db, u1db.Database)

    qPaper = QZPaper(conn)
    for row in qPaper:
        cnt += 1
        #if cnt>5: break

        kwargs = {}
        kwargs['title']   = row['title']
        kwargs['year']    = row['year']
        kwargs['volume']  = row['volume']
        kwargs['issue']   = row['issue']
        kwargs['pages']   = row['pages']
        kwargs['doi']     = row['doi']
        kwargs['url']     = row['url']
        kwargs['date_import'] = row['date_import']

        # author
        qAuthors = QZAuthorsOfPaper(conn, paper=row['_id'])
        authors = []
        for author in qAuthors:
            lname, fname = author['lastname'], author['firstname']
            if not lname is None:
                if not fname is None:
                    authors.append( DataModel.Author(lastname=lname,
                                                     firstname=fname) )
                else:
                    authors.append( DataModel.Author(name=lname) )
            else:
                if not fname is None:
                    authors.append( DataModel.Author(name=fname) )

        if len(authors)>0:
            kwargs['authors'] = authors

        # journal name
        qJournal = QZJournalOfPaper(conn, paper=row['_id'])
        journal = [j for j in qJournal]
        if len(journal)==1:
            kwargs['journal'] = journal[0]['name']

        # tags
        qGroups = QGidsOfPaper(conn, paper=row['_id'])
        tags = []
        for grp in qGroups:
            tags.extend( grp_tags.get(grp['group_id'], []) )

        if len(tags)>0:
            kwargs['tags'] = tags

        if not row['path'] is None:
            pdfpath = os.path.join(basedir, row['path'])
            pdfpath = importFile(pdfpath)
            kwargs['path'] = pdfpath

        p = DataModel.Paper(**kwargs)
        print p

        db.create_doc(p.toDict())


conn = sqlite3.connect(os.path.join(basedir, 'lib.papers'))
db = u1db.open('papers.u1db', create=True)

grp_tags = importGroups(conn)
ftags = open('tags.pkl', 'w')
pickle.dump(grp_tags, ftags)
ftags.close()

importPapers(conn, db, grp_tags)


db.create_index('by-author-name',
                '''combine(split_words(lower(authors)),
                           split_words(lower(authors.lastname)),
                           split_words(lower(authors.firstname)))''')

db.create_index('by-title-words', 'split_words(lower(title))')
db.create_index('by-year',  'year')
db.create_index('by-tags',  'lower(tags)')

db.close()
conn.close()

