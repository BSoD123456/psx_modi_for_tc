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
    ('offset', desc_uint3),
)

mic_sectab_offset = 0x3000

class c_mic_file:

    def __init__(self, raw, sect_size = 0x800, sectab_offs = mic_sectab_offset):
        self.raw = raw
        self.sect_size = 0x800
        self.pos = 0
        self.groups = {}
        self.sectab = {}
        self.sectab_pos = sectab_offs
        self.body_pos = math.inf
        self.scan_done = False

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

    def where(self):
        if self.pos < self.sectab_pos:
            return 'header'
        elif self.pos < self.body_pos:
            return 'sectab'
        else:
            return 'body'

    def scan_header(self):
        if self.pos > 0:
            return
        ent_idx = 0
        while self.where() == 'header':
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

    def scan_sectab(self):
        if self.pos != self.sectab_pos:
            return
        s_idx = 0
        while True:
            c = self.raw[self.pos]
            s_addr = s_idx * self.sect_size
            self.pos += 1
            s_idx += 1
            if c == 1:
                continue
            elif c == 0:
                rlen = len(self.raw)
                if s_addr != rlen:
                    print('invalid sect tab num: 0x{:x}/0x{:x}'.format(
                        s_addr, rlen))
                break
            else:
                self.sectab[s_addr] = c

    def scan_group(self, gid):
        if not gid in self.groups or 'files' in self.groups[gid]:
            return
        grp = self.groups[gid]
        gpos = grp['offset']
        self.pos = gpos
        if not self.where() == 'body':
            print('invalid group offset:', gpos)
            return
        grp['files'] = {}
        last_fdesc = None
        while True:
            dat = self.get_pack(mic_file_entry)
            is_eof = self.isempty(dat['name'])
            if is_eof:
                fname = '__eof__'
            else:
                fname = dat['name'].value.decode().strip('\0')
            f_addr = gpos + dat['offset'].value
            fdesc = {
                'offset': f_addr,
            }
            if last_fdesc:
                last_fdesc['size'] = f_addr - last_fdesc['offset']
            grp['files'][fname] = fdesc
            last_fdesc = fdesc
            if is_eof:
                break

    def scan(self):
        if self.scan_done:
            return
        self.scan_header()
        self.scan_sectab()
        for gid in self.groups:
            self.scan_group(gid)
        self.scan_done = True

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
    
