from PyQt4.QtGui import *
from PyQt4.QtCore import *
import sys, os.path, StringIO, shutil
from datetime import datetime
import GScholar
import popplerqt4
from pybtex.database.input.bibtex import Parser as BibtexParser
from pybtex.core import Entry as BibtexEntry, Person as BibtexPerson
import DataModel
import Utils
import u1db


class DlgImport(QDialog):

    class MatchedPaper(object):
        def __init__(self):
            self.fpath   = None
            self.matches = []
            self.paper   = None

    def __init__(self, parent=None, repoDir=None):
        super(DlgImport, self).__init__(parent)
        self.matchedPaper = self.MatchedPaper()

        if repoDir:
            self.repoDir = repoDir
        else:
            self.repoDir = os.getcwd()
        self.db = u1db.open(os.path.join(self.repoDir, 'papers.u1db'), create=False)

        self.setWindowTitle('Import From PDF Files')

        dlgbox = QVBoxLayout()
        self.setLayout(dlgbox)

        hbox = QHBoxLayout()
        dlgbox.addLayout(hbox)

        # left pane
        vbox = QVBoxLayout()
        hbox.addLayout(vbox)
        hbox.setStretchFactor(vbox, 1)

        hbFile = QHBoxLayout()
        vbox.addLayout(hbFile)
        self._btOpenFiles = QPushButton('Open Files')
        hbFile.addWidget(self._btOpenFiles)
        hbFile.addStretch()

        self._lstFiles = QListWidget()
        self._lstFiles.setMaximumWidth(400)
        self._lstFiles.setMinimumHeight(600)
        vbox.addWidget(self._lstFiles)

        # right pane
        vbox = QVBoxLayout()
        hbox.addLayout(vbox)
        hbox.setStretchFactor(vbox, 5)

        # search box
        hbSearch = QHBoxLayout()
        self._btSearch = QPushButton('Search')
        hbSearch.addWidget(self._btSearch)
        self._leSearch = QLineEdit()
        self._leSearch.setMinimumWidth(600)
        hbSearch.addWidget(self._leSearch)
        vbox.addLayout(hbSearch)

        # search result
        self._tbMatches = QTableWidget()
        self._tbMatches.setMinimumWidth(600)
        vbox.addWidget(self._tbMatches)

        self._tePDF = QPlainTextEdit()
        vbox.addWidget(self._tePDF)

        hbedit = QHBoxLayout()
        vbox.addLayout(hbedit)

        vbtag = QVBoxLayout()
        # Tags
        hbedit.addLayout(vbtag)
        self._trTags = QTreeWidget()
        self._trTags.setMaximumWidth(200)
        self._trTags.setSelectionMode(QAbstractItemView.ExtendedSelection)
        vbtag.addWidget(self._trTags)

        self._btMatch = QPushButton('Match')
        self._btSave  = QPushButton('Save')
        vbtag.addWidget(self._btMatch)
        vbtag.addWidget(self._btSave)

        # edit json
        self._teJson = QPlainTextEdit()
        self._teJson.setLineWrapMode(QPlainTextEdit.NoWrap)
        hbedit.addWidget(self._teJson)


        bbox = QDialogButtonBox(QDialogButtonBox.Close)
        dlgbox.addWidget(bbox)

        self.connect(self._btOpenFiles, SIGNAL('clicked()'), self.openFiles)
        self.connect(self._lstFiles, SIGNAL('itemActivated(QListWidgetItem*)'), self.extractFile)
        self.connect(self._btSearch, SIGNAL('clicked()'), self.searchGoogle)
        self.connect(self._leSearch, SIGNAL('returnPressed()'), self.searchGoogle)
        self.connect(self._btMatch,  SIGNAL('clicked()'), self.selectMatch)
        self.connect(self._btSave,   SIGNAL('clicked()'), self.savePaper)
        self.connect(bbox, SIGNAL('rejected()'), self.reject)
        self.connect(self, SIGNAL('rejected()'), self.onQuit)

        self.initMatchTable()
        self.getTags()

        self.browser = GScholar.Browser()

    def getTags(self):

        fntag = os.path.join(self.repoDir, 'tags.json')
        if os.path.exists(fntag):
            f = open(fntag)
            self.tagTree = DataModel.TagTree.fromJson(f.read())
            f.close()
        else:
            self.tagTree = DataModel.TagTree()

        def addTagItem(pitm, pparts, tree):
            for tag, subtree in tree.children():
                parts = [tag] + pparts
                fulltag = ':'.join(parts)

                tags = []
                for i in xrange(len(parts)):
                    tags.append(':'.join(parts[i:]))

                itm = QTreeWidgetItem([tag])
                itm.setData(0, Qt.UserRole, tags)

                if pitm:
                    pitm.addChild(itm)
                else:
                    self._trTags.addTopLevelItem(itm)

                addTagItem(itm, parts, subtree)

        self._trTags.clear()
        addTagItem(None, [], self.tagTree)

    def saveTags(self, nTagTree):
        for i in [2, 1, 0]:
            fnbaka = os.path.join(self.repoDir, 'tags.json.%d.bak'%i)
            fnbakb = os.path.join(self.repoDir, 'tags.json.%d.bak'%(i+1))
            if os.path.exists(fnbakb): os.remove(fnbakb)
            if os.path.exists(fnbaka): os.rename(fnbaka, fnbakb)

        fnbaka = os.path.join(self.repoDir, 'tags.json')
        fnbakb = os.path.join(self.repoDir, 'tags.json.0.bak')
        if os.path.exists(fnbaka):
            os.rename(fnbaka, fnbakb)

        f = open('tags.json', 'w')
        f.write(self.tagTree.toJson())
        f.close()

        self.getTags()


    def openFiles(self):
        lst = QFileDialog.getOpenFileNames(self, 'Open PDF Files', '.', 'PDF files(*.pdf)')
        for fname in lst:
            fpath = os.path.normpath(str(fname))
            fname = os.path.basename(str(fname))
            itm = QListWidgetItem(fname)
            itm.setData(Qt.UserRole, fpath)
            self._lstFiles.addItem(itm)

    @staticmethod
    def _extractFromPDF(fpath):
        doc = popplerqt4.Poppler.Document.load(fpath)
        isinstance(doc, popplerqt4.Poppler.Document)

        title = doc.info('Title')

        pg1 = doc.page(0)
        txt = QString()
        pRect = None
        for w in pg1.textList()[:300]:
            rect = w.boundingBox()
            isinstance(rect, QRectF)

            if not pRect is None:
                z1 = pRect.bottom()
                z2 = rect.top()

                if z2 > z1:
                    nl = int((z2-z1)/10.)+1
                    for i in xrange(nl): txt.append('\n')

            txt.append(w.text())
            if w.hasSpaceAfter(): txt.append(' ')

            pRect = rect

        return title, txt

    def extractFile(self, itm):
        if not isinstance(itm, QListWidgetItem):
            raise TypeError

        fpath = str(itm.data(Qt.UserRole).toString())

        title, txt = self._extractFromPDF(fpath)
        self._leSearch.setText(title)
        self._tePDF.setPlainText(txt)
        self.initMatchTable()

        self.matchedPaper = self.MatchedPaper()
        self.matchedPaper.fpath = fpath
        self.initMatchTable()

    def initMatchTable(self):
        self.matchedPaper.matches = []
        while self._tbMatches.rowCount()>0:
            self._tbMatches.removeRow(0)
        while self._tbMatches.columnCount()>0:
            self._tbMatches.removeColumn(0)

        cols    = ['Title', 'Authors', 'Journal', 'Year']
        widths  = [500, 250, 220, 80]
        self._tbMatches.setColumnCount(len(cols))
        for i, (l,w) in enumerate(zip(cols, widths)):
            self._tbMatches.setColumnWidth(i, w)
        self._tbMatches.setHorizontalHeaderLabels(cols)

    def searchGoogle(self):
        self.initMatchTable()

        search = unicode(self._leSearch.text())
        query = GScholar.SearchQuery(self.browser, search)

        articles = query.request()
        if len(articles)==0:
            QMessageBox.warning(self, 'Warning', 'No match found in google scholar...')

        def cellStr(field):
            v = article[field]
            if v is None: return '?'
            else:         return v

        for article in articles:
            r = self._tbMatches.rowCount()
            self._tbMatches.insertRow(r)
            self._tbMatches.setItem(r, 0, QTableWidgetItem(cellStr('title')))
            self._tbMatches.setItem(r, 1, QTableWidgetItem(cellStr('authors')))
            self._tbMatches.setItem(r, 2, QTableWidgetItem(cellStr('journal')))
            self._tbMatches.setItem(r, 3, QTableWidgetItem(cellStr('year')))

            self.matchedPaper.matches.append(article)

        self._tbMatches.setCurrentCell(0,0)

    def selectMatch(self):
        pdfpath, isNew = Utils.importFile(self.matchedPaper.fpath)
        if not isNew:
            QMessageBox.warning(self, 'Warning', 'File already in repository!')

        row = self._tbMatches.currentRow()
        if row>=0 and row<len(self.matchedPaper.matches):
            article = self.matchedPaper.matches[row]
            paper = self.makePaperObj(article)

        else:
            # an empty template paper
            paper = DataModel.Paper(
                title   = u'Title',
                year    = 2000,
                authors = [DataModel.Author(firstname='Firstname', lastname='Lastname')],
                journal = u'Journal Name',
                volume  = u'1',
                issue   = u'1',
                pages   = u'1-10',
                )

        # tags
        tags = []
        for idx in self._trTags.selectedIndexes():
            itm = self._trTags.itemFromIndex(idx)
            lst = itm.data(0, Qt.UserRole).toStringList()
            for tag in lst:
                tags.append(unicode(tag))
        paper.tags = tags

        paper.path    = pdfpath
        paper.date_import = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

        self.matchedPaper.paper = paper
        self._teJson.setPlainText(self.matchedPaper.paper.toJson())

    def makePaperObj(self, article):
        kwargs = {}

        # first from google search result page
        kwargs['title']         =   article['title']
        authors                 =   []
        for author in article['authors'].split(','):
            parts = author.split()
            if len(parts)>1:
                authors.append(DataModel.Author(firstname=' '.join(parts[:-1]),
                                                lastname=parts[-1] ))
            else:
                authors.append(DataModel.Author(name=author.strip()))
        kwargs['authors']       =   authors
        kwargs['journal']       =   article['journal']
        kwargs['url']           =   article['url']
        kwargs['year']          =   int(article['year'])

        # if google provides a bibtex download, use it
        if article['url_bibtex']:
            q = GScholar.Query(self.browser, article['url_bibtex'])
            bibtex = q.request()

            bib_data = BibtexParser().parse_stream(StringIO.StringIO(bibtex))

            bib_ent = bib_data.entries.values()[0]
            if not isinstance(bib_ent, BibtexEntry):
                raise TypeError

            kwargs['title']     = bib_ent.fields['title']
            kwargs['year']      = int(bib_ent.fields['year'])
            if bib_ent.fields.has_key('journal'):
                kwargs['journal']   = bib_ent.fields['journal']
            elif bib_ent.fields.has_key('booktitle'):
                kwargs['journal']   = bib_ent.fields['booktitle']
            if bib_ent.fields.has_key('volume'):
                kwargs['volume']    = bib_ent.fields['volume']
            if bib_ent.fields.has_key('number'):
                kwargs['issue']     = bib_ent.fields['number']
            if bib_ent.fields.has_key('pages'):
                kwargs['pages']     = bib_ent.fields['pages']
            authors = []
            for person in bib_ent.persons['author']:
                if not isinstance(person, BibtexPerson):
                    raise TypeError

                fname = u' '.join(person.bibtex_first())
                lname = u' '.join(person.prelast() + person.last() + person.lineage())
                if len(fname)>0:
                    authors.append(DataModel.Author(firstname=fname, lastname=lname))
                else:
                    authors.append(DataModel.Author(name=lname))
            kwargs['authors']   = authors


        return DataModel.Paper(**kwargs)

    def savePaper(self):
        abort = False

        paper = DataModel.Paper.fromJson(unicode(self._teJson.toPlainText()))

        lstNewTag = []
        nTagTree = DataModel.TagTree(self.tagTree)
        for fulltag in paper.tags:
            parts = fulltag.split(':')

            tr = nTagTree
            for tag in reversed(parts):
                if not tag in tr:
                    lstNewTag.append(fulltag)
                tr = tr[tag]

        if len(lstNewTag)>0:
            ret = QMessageBox.question(self, 'New tags',
                                       'Add the following new tags? %s' % ', '.join(lstNewTag),
                                       QMessageBox.Yes|QMessageBox.No, QMessageBox.Yes)
            if not ret==QMessageBox.Yes:
                abort = True

        if abort:
            return

        self.saveTags(nTagTree)
        self.db.create_doc(paper.toDict())

        QMessageBox.information(self, 'Save', 'Paper Saved.')

        self.matchedPaper = self.MatchedPaper()
        self.initMatchTable()
        self._tePDF.clear()
        self._teJson.clear()

    def onQuit(self):
        print 'exiting'
        self.db.close()


if __name__ == '__main__':

    app = QApplication(sys.argv)

    dlg = DlgImport()
    dlg.show()

    app.exec_()



