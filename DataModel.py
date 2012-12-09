__all__=['Author', 'Paper', 'TagTree']

import json
from collections import defaultdict

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

class Author(object):
    def __init__(self, **kwargs):
        self.lastname   = kwargs.get('lastname')
        self.firstname  = kwargs.get('firstname')
        self.name       = kwargs.get('name')

    def toDict(self):
        if self.lastname:
            if self.firstname:
                return {'lastname': self.lastname,
                        'firstname': self.firstname,
                        }
            else:
                return self.lastname
        else:
            return self.name

    @staticmethod
    def fromDict(dct):
        if isinstance(dct, dict):
            return Author(**dct)
        else:
            return Author(name=dct)

    def __str__(self):
        if self.lastname:
            if self.firstname:
                return '%s %s' % (senc(self.firstname),
                                  senc(self.lastname))
            else:
                return senc(self.lastname)
        else:
            if self.firstname:
                return senc(self.firstname)
            else:
                return ''

    def __unicode__(self):
        if self.lastname:
            if self.firstname:
                return u'%s %s' % (self.firstname,
                                   self.lastname)
            else:
                return self.lastname
        else:
            if self.firstname:
                return self.firstname
            else:
                return u''


class Paper(object):
    def __init__(self, **kwargs):
        self.doc_id     = kwargs.get('doc_id')
        self.title      = kwargs.get('title')
        self.year       = kwargs.get('year')
        self.authors    = kwargs.get('authors')
        self.journal    = kwargs.get('journal')
        self.volume     = kwargs.get('volume')
        self.issue      = kwargs.get('issue')
        self.pages      = kwargs.get('pages')
        self.doi        = kwargs.get('doi')
        self.url        = kwargs.get('url')
        self.path       = kwargs.get('path')
        self.tags       = kwargs.get('tags')
        self.date_import= kwargs.get('date_import')

    def toDict(self):
        res = {}
        for key in '''title year authors journal volume issue pages
                    doi url path tags date_import'''.split():
            val = getattr(self, key)
            if val is None: continue

            if key=='authors':
                res[key] = [author.toDict() for author in val]
            else:
                res[key] = val
        return res

    @staticmethod
    def fromDict(dct):
        if not isinstance(dct, dict): raise TypeError

        kwargs = {}
        for key in '''title year authors journal volume issue pages
                    doi url path tags date_import'''.split():
            if not dct.has_key(key): continue
            val = dct[key]

            if key=='authors':
                kwargs[key] = [Author.fromDict(author) for author in val]
            else:
                kwargs[key] = val

        return Paper(**kwargs)

    def __str__(self):
        res=[]
        sauthor = []
        if not self.authors is None:
            for author in self.authors:
                sauthor.append(str(author))
            res.append(', '.join(sauthor))

        if not self.title is None:
            res.append(senc(self.title))

        if not self.journal is None:
            res.append(senc(self.journal))

        if not self.volume is None:
            res.append(senc(self.volume))

        if not self.pages is None:
            res.append(senc(self.pages))

        if not self.year is None:
            res.append(senc(self.year))

        stags=[]
        if not self.tags is None:
            for tag in self.tags:
                stags.append(str(tag))
            res.append(', '.join(stags))

        return '; '.join(res)

    def toJson(self):
        dct = self.toDict()
        return json.dumps(dct, ensure_ascii=False, indent=2)

    @staticmethod
    def fromJson(sJson):
        return Paper.fromDict(json.loads(sJson))

def _tree():
    return defaultdict(_tree)

class TagTree(object):

    def __init__(self, tree=None):
        if tree is None:
            self._tree = _tree()
        else:
            self._tree = tree

    def __contains__(self, tag):
        return tag in self._tree

    def __getitem__(self, tag):
        return self._tree[tag]

    def childCount(self):
        return len(self._tree)

    def children(self):
        return [(k,TagTree(self._tree[k])) for k in sorted(self._tree.keys())]

    def toDict(self):
        return {k: TagTree(v).toDict() for k,v in self._tree.iteritems()}

    @staticmethod
    def fromDict(dct):
        def doDct(t, d):
            for k,v in d.iteritems():
                t[k]
                doDct(t[k], v)

        tree = TagTree()
        doDct(tree, dct)

        return tree

    def toJson(self):
        dct = self.toDict()
        return json.dumps(dct, ensure_ascii=False, indent=2)

    @staticmethod
    def fromJson(sJson):
        return TagTree.fromDict(json.loads(sJson))


if __name__=='__main__':
    taxonomy = TagTree()

    taxonomy['Animalia']['Chordata']['Mammalia']['Carnivora']['Felidae']['Felis']['cat']
    taxonomy['Animalia']['Chordata']['Mammalia']['Carnivora']['Felidae']['Panthera']['lion']
    taxonomy['Animalia']['Chordata']['Mammalia']['Carnivora']['Canidae']['Canis']['dog']
    taxonomy['Animalia']['Chordata']['Mammalia']['Carnivora']['Canidae']['Canis']['coyote']
    taxonomy['Plantae']['Solanales']['Solanaceae']['Solanum']['tomato']
    taxonomy['Plantae']['Solanales']['Solanaceae']['Solanum']['potato']
    taxonomy['Plantae']['Solanales']['Convolvulaceae']['Ipomoea']['sweet potato']

    print taxonomy.children()
    print taxonomy.children()[0][0]
    print taxonomy.children()[0][1].toDict()

    print '----------'
    print taxonomy.toDict()

    print '----------'
    print TagTree.fromDict(taxonomy.toDict()).toDict()


    print '----------'
    print 'Animalia' in taxonomy
    print 'Chordata' in taxonomy['Animalia']
    print 'XXX' in taxonomy['Animalia']
