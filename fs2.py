#!/usr/bin/env python

import logging

from collections import defaultdict
from errno import ENOENT
from stat import S_IFDIR, S_IFLNK, S_IFREG
import os, os.path
import datetime, calendar
from sys import argv, exit
from time import time

from fusepy import FUSE, FuseOSError, Operations, LoggingMixIn

import u1db
import DataModel
import re
from Utils import *

if not hasattr(__builtins__, 'bytes'):
    bytes = str

def senc(s):
    if isinstance(s, unicode):
        try:
            return s.encode('utf8')
        except:
            return ''
    elif isinstance(s, str):
        return s
    else:
        return str(s)

def cleanFilename(fname):
    for pat, sub in [ ('\/',    u'\u2215'), ('\\\\', '_'),
                      ('\?',    '_'),
                      ('%',     '_'),
                      ('\*',    '_'),
                      (':',     '_'),
                      ('"',     '\''),
                      ('\n',    ' '),
                      ('\r',    ' '),
                      ]:
        fname = re.sub(pat, sub, fname)

    return fname


class Stat(object):
    """
    A Stat object. Describes the attributes of a file or directory.
    Has all the st_* attributes, as well as dt_atime, dt_mtime and dt_ctime,
    which are datetime.datetime versions of st_*time. The st_*time versions
    are in epoch time.
    """
    # Filesize of directories, in bytes.
    DIRSIZE = 4096

    # We can define __init__ however we like, because it's only called by us.
    # But it has to have certain fields.
    def __init__(self, path_or_st_mode, st_size=0, st_nlink=1, st_uid=None, st_gid=None,
            dt_atime=None, dt_mtime=None, dt_ctime=None):
        """
        Creates a Stat object.
        st_mode: Required. Should be stat.S_IFREG or stat.S_IFDIR ORed with a
            regular Unix permission value like 0644.
        st_size: Required. Size of file in bytes. For a directory, should be
            Stat.DIRSIZE.
        st_nlink: Number of hard-links to the file. Regular files should
            usually be 1 (default). Directories should usually be 2 + number
            of immediate subdirs (one from the parent, one from self, one from
            each child).
        st_uid, st_gid: uid/gid of file owner. Defaults to the user who
            mounted the file system.
        st_atime, st_mtime, st_ctime: atime/mtime/ctime of file.
            (Access time, modification time, stat change time).
            These must be datetime.datetime objects, in UTC time.
            All three values default to the current time.
        """
        if isinstance(path_or_st_mode, basestring):
            fpath = path_or_st_mode
            st = os.stat(fpath)

            self.st_mode    = st.st_mode
            self.st_nlink   = st.st_nlink
            self.st_uid     = st.st_uid
            self.st_gid     = st.st_gid
            self.st_size    = st.st_size
            self.st_atime   = st.st_atime
            self.st_mtime   = st.st_mtime
            self.st_ctime   = st.st_ctime
            return

        else:
            st_mode = path_or_st_mode

        self.st_mode = st_mode
        self.st_ino = 0         # Ignored, but required
        self.st_dev = 0         # Ignored, but required
        # Note: Wiki says st_blksize is required (like st_dev, ignored but
        # required). However, this breaks things and another tutorial I found
        # did not have this field.
        self.st_nlink = st_nlink
        if st_uid is None:
            st_uid = os.getuid()
        self.st_uid = st_uid
        if st_gid is None:
            st_gid = os.getgid()
        self.st_gid = st_gid
        self.st_size = st_size
        now = datetime.datetime.utcnow()
        self.dt_atime = dt_atime or now
        self.dt_mtime = dt_mtime or now
        self.dt_ctime = dt_ctime or now

    def toDict(self):
        return dict(st_mode=self.st_mode,   st_nlink=self.st_nlink,
                    st_uid=self.st_uid,     st_gid=self.st_gid,
                    st_size=self.st_size,   st_atime=self.st_atime,
                    st_mtime=self.st_mtime, st_ctime=self.st_ctime)

    def __repr__(self):
        return ("<Stat st_mode %s, st_nlink %s, st_uid %s, st_gid %s, "
            "st_size %s>" % (self.st_mode, self.st_nlink, self.st_uid,
            self.st_gid, self.st_size))

    def _get_dt_atime(self):
        return self.epoch_datetime(self.st_atime)
    def _set_dt_atime(self, value):
        self.st_atime = self.datetime_epoch(value)
    dt_atime = property(_get_dt_atime, _set_dt_atime)

    def _get_dt_mtime(self):
        return self.epoch_datetime(self.st_mtime)
    def _set_dt_mtime(self, value):
        self.st_mtime = self.datetime_epoch(value)
    dt_mtime = property(_get_dt_mtime, _set_dt_mtime)

    def _get_dt_ctime(self):
        return self.epoch_datetime(self.st_ctime)
    def _set_dt_ctime(self, value):
        self.st_ctime = self.datetime_epoch(value)
    dt_ctime = property(_get_dt_ctime, _set_dt_ctime)

    @staticmethod
    def datetime_epoch(dt):
        """
        Converts a datetime.datetime object which is in UTC time
        (as returned by datetime.datetime.utcnow()) into an int, which represents
        the number of seconds since the system epoch (also in UTC time).
        """
        # datetime.datetime.timetuple converts a datetime into a time.struct_time.
        # calendar.timegm converts a time.struct_time into epoch time, without
        # modifying for time zone (so UTC time stays in UTC time, unlike
        # time.mktime).
        return calendar.timegm(dt.timetuple())
    @staticmethod
    def epoch_datetime(seconds):
        """
        Converts an int, the number of seconds since the system epoch in UTC
        time, into a datetime.datetime object, also in UTC time.
        """
        return datetime.datetime.utcfromtimestamp(seconds)

    def set_times_to_now(self, atime=False, mtime=False, ctime=False):
        """
        Sets one or more of atime, mtime and ctime to the current time.
        atime, mtime, ctime: All booleans. If True, this value is updated.
        """
        now = datetime.datetime.utcnow()
        if atime:
            self.dt_atime = now
        if mtime:
            self.dt_mtime = now
        if ctime:
            self.dt_ctime = now

    def check_permission(self, uid, gid, flags):
        """
        Checks the permission of a uid:gid with given flags.
        Returns True for allowed, False for denied.
        flags: As described in man 2 access (Linux Programmer's Manual).
            Either os.F_OK (test for existence of file), or ORing of
            os.R_OK, os.W_OK, os.X_OK (test if file is readable, writable and
            executable, respectively. Must pass all tests).
        """
        if flags == os.F_OK:
            return True
        user = (self.st_mode & 0700) >> 6
        group = (self.st_mode & 070) >> 3
        other = self.st_mode & 07
        if uid == self.st_uid:
            # Use "user" permissions
            mode = user | group | other
        elif gid == self.st_gid:
            # Use "group" permissions
            # XXX This will only check the user's primary group. Don't we need
            # to check all the groups this user is in?
            mode = group | other
        else:
            # Use "other" permissions
            mode = other
        if flags & os.R_OK:
            if mode & os.R_OK == 0:
                return False
        if flags & os.W_OK:
            if mode & os.W_OK == 0:
                return False
        if flags & os.X_OK:
            if uid == 0:
                # Root has special privileges. May execute if anyone can.
                if mode & 0111 == 0:
                    return False
            else:
                if mode & os.X_OK == 0:
                    return False
        return True


class FSObject(object):
    """
    A file system object (subclasses are File and Dir).
    Attributes:
    name: str
    stat: Stat
    parent: Dir or None
    """
    def __repr__(self):
        return "<%s %s>" % (type(self).__name__, self.name)

    def newFileHandle(self, obj=None):
        if not self.parent is None:
            return self.parent.newFileHandle(obj)

class SearchResult(FSObject):
    '''
    Search result as a directory
    '''
    class Iter(object):
        def __init__(self, res):
            self.res = res
            self.curDot  = 0 # cursor for . and ..
            self.curSrch = 0 # cursor for sub-searches
            self.curPapr = 0 # cursor for papers

        def next(self):
            if self.curDot==0:
                self.curDot = 1
                return '.'
            elif self.curDot==1:
                self.curDot = 2
                return '..'

            if self.curSrch<len(self.res.searches):
                r = self.res.searches[self.curSrch]
                self.curSrch += 1
                if isinstance(r, SearchResult):
                    return r.name

            if self.curPapr<len(self.res.papers):
                r = self.res.papers[self.curPapr]
                self.curPapr += 1
                return r

            raise StopIteration

        def __iter__(self):
            return self

    def __init__(self, db, name, parent):
        if not isinstance(db, u1db.Database):
            raise TypeError
        self.db = db
        self.name = name
        self.parent = parent
        self.fh = self.newFileHandle(self)

        self.papers = []
        self.mapPapers = {}
        self.stat = Stat(S_IFDIR|0755, Stat.DIRSIZE, st_nlink=2)

        def _incName(fname0):
            fname = fname0
            cnt = 1
            while self.mapPapers.has_key(fname):
                fname = u'%s(%d)' % (fname0, cnt)
                cnt += 1
            return fname

        _, docs = self.db.get_all_docs()
        for doc in docs:
            if not isinstance(doc, u1db.Document): continue

            paper = DataModel.Paper.fromDict(doc.content)
            if not paper.title is None and len(paper.title)>0:
                title = _incName(cleanFilename(paper.title))
            else:
                title = _incName('Untitled')
            self.mapPapers[title] = paper
            self.papers.append(title)
        self.statPapers = Stat(S_IFDIR|0755, Stat.DIRSIZE, st_nlink=2)

        self.searches = []
        self.parent = parent

    def getattr(self, fname=None):
        if fname is None: return self.stat.toDict()

        if self.mapPapers.has_key(fname):
            return self.statPapers.toDict()
        raise FuseOSError(ENOENT)

    def opendir(self, fname):
        if self.mapPapers.has_key(fname):
            dirPaper = DirPaper(fname, stat=self.statPapers, parent=self)
            return dirPaper.fh

    def readdir(self):
        return SearchResult.Iter(self)

class DirPaper(FSObject):
    '''
    Paper as a directory
    '''

    def __init__(self, name, parent, stat=None):
        self.name = name
        self.parent=parent
        if stat:
            self.stat=stat
        else:
            self.stat=Stat(S_IFDIR|0755, Stat.DIRSIZE, st_nlink=2)

        self.fh = self.newFileHandle(self)

        paper = self.parent.mapPapers[self.name]
        self.pdf = None
        if not paper.path is None:
            self.pdf = PDFFile(u'%s.pdf'%cleanFilename(paper.title),
                               os.path.join(repoDir, paper.path[0:2], paper.path),
                               self)

    def getattr(self, fname=None):
        if fname is None: return self.stat.toDict()

        if self.pdf and fname==self.pdf.name:
            return self.pdf.getattr()
        raise FuseOSError(ENOENT)

    def opendir(self, fname):
        return None     # no more sub dir

    def open(self, fname, flags):
        if self.pdf and fname==self.pdf.name:
            return self.pdf.open(flags)
        raise FuseOSError(ENOENT)

    def readdir(self):
        lst = ['.', '..']
        if self.pdf:
            lst.append(self.pdf.name)
        return lst

class FileObject(FSObject):
    pass

class PDFFile(FileObject):
    '''
    PDF File
    '''
    def __init__(self, name, osPath, parent):
        self.name = name
        self.osPath = osPath
        self.parent = parent

        self.osfd = {} # map FUSE file descriptor to OS file descriptors

    def getattr(self):
        return Stat(self.osPath).toDict()

    def open(self, flags):
        osfd = os.open(self.osPath, flags)
        fh = self.newFileHandle(self)
        self.osfd[fh] = osfd

        return fh

    def read(self, fh, size, offset):
        osfd = self.osfd[fh]
        os.lseek(osfd, offset, os.SEEK_SET)
        return os.read(osfd, size)

    def release(self, fh):
        osfd = self.osfd[fh]
        os.close(osfd)
        del self.osfd[fh]

class PaperFS(LoggingMixIn, Operations):
    'Example memory filesystem. Supports only one level of files.'

    def __init__(self):
        self.mapPath = {}
        self.mapHandle = {}
        self.cntFH = 0

        self.db = u1db.open('papers.u1db', create=False)

        root = SearchResult(self.db, 'Papers', parent=self)
        self.mapPath['/'] = root

    def newFileHandle(self, obj=None):
        fh = self.cntFH
        if not obj is None:
            self.mapHandle[fh] = obj
        self.cntFH += 1
        return fh

    def _search_path(self, path):
        pname, fname, fsobj = path, '', None

        fsobj = self.mapPath.get(pname)
        if fsobj is None:
            pname, fname = os.path.split(pname)
            fsobj = self.mapPath.get(pname)

        return fsobj, fname

    def opendir(self, path):
        if path in self.mapPath:
            return self.mapPath[path].fh

        fsobj, fname = self._search_path(path)
        if isinstance(fsobj, FSObject):
            fh = fsobj.opendir(fname)
            dobj = self.mapHandle.get(fh)
            if not dobj is None:
                self.mapPath[path] = dobj
            return fh

        raise FuseOSError(ENOENT)

    #def releasedir(self, path, fh):
    #    del self.mapHandle[fh]

    def readdir(self, path, fh=None):
        if fh is None:
            fsobj, fname = self._search_path(path)
        else:
            fsobj, fname = self.mapHandle.get(fh), None

        if isinstance(fsobj, SearchResult):
            return fsobj.readdir()
        elif isinstance(fsobj, DirPaper):
            return fsobj.readdir()
        else:
            return ['.', '..']

    def getattr(self, path, fh=None):
        fsobj, fname = None, None
        if fh is None:
            pname, fname = os.path.split(path)
            fh = self.opendir(pname)

        fsobj = self.mapHandle.get(fh)

        if isinstance(fsobj, FSObject):
            if fname:
                return fsobj.getattr(fname)
            else:
                return fsobj.getattr()

        raise FuseOSError(ENOENT)


    def open(self, path, flags):
        fsobj, fname = self._search_path(path)

        if isinstance(fsobj, FSObject):
            if fname:
                fh = fsobj.open(fname, flags)
            else:
                fh = fsobj.open(flags)

            fobj = self.mapHandle.get(fh)
            if fobj:
                self.mapPath[path] = fobj
            return fh

        raise FuseOSError(ENOENT)

    def release(self, path, fh):
        fobj = self.mapHandle.get(fh)
        if isinstance(fobj, FileObject):
            fobj.release(fh)
            del self.mapHandle[fh]

    def read(self, path, size, offset, fh):
        fobj = self.mapHandle.get(fh)

        if isinstance(fobj, FSObject):
            return fobj.read(fh, size, offset)

        raise FuseOSError(ENOENT)

if __name__ == '__main__':
    if len(argv) != 2:
        print('usage: %s <mountpoint>' % argv[0])
        exit(1)

    logging.getLogger().setLevel(logging.DEBUG)
    fuse = FUSE(PaperFS(), argv[1], foreground=True)
