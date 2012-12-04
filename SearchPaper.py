__all__=['Search', 'AllPapers', 'ByAuthorName', 'ByTag',
         'IndexByAuthor', 'IndexByTag']

import u1db
import DataModel

class Search(object):
    def __init__(self, db):
        self.db = db
        self._papers = None

    def execute(self):
        if not self._papers is None: return

    def papers(self):
        return self._papers

    def _docs2papers(self, docs):
        self._papers = []
        for doc in docs:
            if not isinstance(doc, u1db.Document): continue

            paper = DataModel.Paper.fromDict(doc.content)
            self._papers.append(paper)

class Index(object):
    def __init__(self, db):
        if not isinstance(db, u1db.Database):
            raise TypeError

        self.db = db
        self._keys = []

    def keys(self):
        return self._keys

    def get(self, key):
        return None

class AllPapers(Search):
    def __init__(self, db):
        super(AllPapers, self).__init__(db)

    def execute(self):
        super(AllPapers, self).execute()

        _, docs = self.db.get_all_docs()
        self._docs2papers(docs)

class ByAuthorName(Search):
    def __init__(self, db, key):
        super(ByAuthorName, self).__init__(db)

        self.key = key

    def execute(self):
        isinstance(self.db, u1db.Database)
        docs = self.db.get_from_index('by-author-name', self.key)
        self._docs2papers(docs)

class IndexByAuthor(Index):
    def __init__(self, db):
        super(IndexByAuthor, self).__init__(db)
        self._keys = []
        for k, in db.get_index_keys('by-author-name'):
            self._keys.append(k)

    def get(self, key):
        return ByAuthorName(self.db, key)


class ByTag(Search):
    def __init__(self, db, key):
        super(ByTag, self).__init__(db)

        self.key = key

    def execute(self):
        isinstance(self.db, u1db.Database)
        docs = self.db.get_from_index('by-tags', self.key)
        self._docs2papers(docs)

class IndexByTag(Index):
    def __init__(self, db):
        super(IndexByTag, self).__init__(db)
        self._keys = []
        for k, in db.get_index_keys('by-tags'):
            self._keys.append(k)

    def get(self, key):
        return ByTag(self.db, key)

