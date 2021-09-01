#! python3
# coding: utf-8

import os, os.path
import math
import itertools, functools

import stat_parser as sp

desc_uint3 = sp.c_desc_int(3)

mic_group_entry = sp.desc_pack(
    ('offset', sp.desc_uint),
    ('size', sp.desc_uint),
    ('uk_addr', sp.desc_uint),
    ('uk_hash', sp.desc_uint),
)

mic_file_entry = sp.desc_pack(
    ('name', sp.desc_buf(13)),
    ('size', desc_uint3),
)

class c_mic_file:

    def __init__(self, raw, sect_size = 0x800):
        self.raw = raw
        self.sect_size = 0x800
        self.pos = 0
        self.groups = {}
        self.body_pos = math.inf

    def get_pack(self, desc, noshift = False):
        if self.pos >= len(self.raw):
            return None
        spos = self.pos
        dpos = spos + len(desc)
        if not noshift:
            self.pos = dpos
        return sp.data_pack(desc,
                            self.raw[spos:dpos])

    @staticmethod
    def isempty(dat):
        buf = dat.buffer()
        return buf == b'\0' * len(buf)

    def in_header(self):
        return self.pos < self.body_pos

    def get_next_group_entry(self):
        return 

    def scan_header(self):
        if self.pos > 0:
            return
        ent_idx = 0
        while self.in_header():
            dat = self.get_pack(mic_group_entry)
            if dat['size'].value == 0:
                if not self.isempty(dat):
                    print('invalid group entry:', dat.buffer())
            else:
                o_sec = dat['offset'].value
                s_sec = dat['size'].value
                o_addr = o_sec * self.sect_size
                s_addr = s_sec * self.sect_size
                self.groups[ent_idx] = {
                    'offset': o_addr,
                    'size': s_addr,
                }
                if o_addr < self.body_pos:
                    self.body_pos = o_addr
            ent_idx += 1


def tst_find_kw(raw, kw = b'PROG.BIN'):
    pos = 0
    rs = []
    while True:
        rpos = raw.find(kw, pos)
        if rpos < 0:
            break
        pos = rpos + 1
        rs.append(rpos)
    rs.append(len(raw))
    return rs

if __name__ == '__main__':
    
    work_path = r'G:\emu\ps\jpsxdec_v1-00_rev3921\extable\l3t1\LINDA'
    dest_file = 'LINDA.MIC'
    
    with open(os.path.join(work_path, dest_file), 'rb') as fd:
        raw = fd.read()

    from pprint import pprint as ppr

    dltrs = lambda rs: functools.reduce(
        lambda r, a: r.append(a - r.pop()) or r.append(a) or r, rs, [0])[:-1]

    foo = tst_find_kw(raw)
    bar = dltrs(foo)
    foobar = [(hex(a), hex(int(b/0x800))) for a, b in zip(foo[:-1], bar[1:])]

    mf = c_mic_file(raw)
    
