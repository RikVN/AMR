#!/usr/bin/env python3
# encoding=utf-8

trans_table = {
    u".": u"PUNKTS",
    u",": u"KOMATS",
    u";": u"SEMIKOLS",
    u":": u"KOLS",
    u"'": u"APASTROFS1",
    u"`": u"APASTROFS2",
    u" ": u"TUKSUMS",
    u"(": u"ATVEROSAIEKAVA",
    u")": u"AIZVEROSAIEKAVA",
    u"£": u"MARCINA",
    u"$": u"ZALIE",
    u"&": u"UNZIME",
    u"@": u"ATZIME",
    u"€": u"EIRAS",
    u"/": u"SLIPSVITRA",
}

reverse_trans_table = {v:k for k,v in trans_table.items()}

import re

notranslatere = re.compile(r'^.*[\s'+''.join(trans_table.keys())+r'].*$')

def translate(s):
    if not notranslatere.match(s):
        return s
    #     return s[1:-1]
    # s = s[1:-1]
    for k,v in trans_table.items():
        s = s.replace(k,v)
    return '_'+s

def restore(s):
    if s and s[0] == '_':
        s = s[1:]
        for k,v in reverse_trans_table.items():
            s = s.replace(k,v)
    return '"%s"' % s


if __name__ == "__main__":

    example = """On 27 August 2007 Iran and the U.N.'s International Atomic Energy Agency released a plan for resolving issues by December 2007."""
    example = '''"jānis"'''
    example = '''"jānis."'''

    print(example)
    r = translate(example)
    print(r)
    r = restore(r)
    print(r)
    print(example == r)


