__all__=['Search', 'AllPapers']

import u1db
import DataModel

class Search(object):
    def execute(self):
        pass

    def papers(self):
        return []

class AllPapers(Search):
    def __init__(self, db):
        self.db = db
        self._papers = None

    def execute(self):
        if not self._papers is None: return

        self._papers = []
        _, docs = self.db.get_all_docs()
        for doc in docs:
            if not isinstance(doc, u1db.Document): continue

            paper = DataModel.Paper.fromDict(doc.content)
            self._papers.append(paper)

    def papers(self):
        return self._papers

