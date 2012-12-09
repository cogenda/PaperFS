__all__=['importFile']

import os, os.path, shutil
import hashlib

def digest_for_file(f, block_size=2**20):
    h = hashlib.sha1()
    while True:
        data = f.read(block_size)
        if not data:
            break
        h.update(data)
    return h.hexdigest()

def importFile(src, repoDir):
    if not os.path.exists(src):
        return None, False

    f = open(src, 'rb')
    dig = digest_for_file(f)
    f.close()

    dpath = os.path.join(repoDir, dig[0:2])
    if not os.path.exists(dpath):
        os.makedirs(dpath)

    fname = '%s%s' % (dig, os.path.splitext(src)[-1])
    fpath = os.path.join(dpath, fname)
    isNew = False
    if not os.path.exists(fpath):
        isNew = True
        shutil.copy2(src, os.path.join(dpath, fname))

    return fname, isNew
