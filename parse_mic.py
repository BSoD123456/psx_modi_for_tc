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
        self.curdir = []

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

    def relpath(self, path):
        ps = path.split('/')
        if len(ps) > 1 and not ps[0]:
            rcd = []
        else:
            rcd = self.curdir.copy()
        for p in ps:
            if not p or p == '.':
                continue
            elif p == '..':
                if rcd:
                    rcd.pop()
                continue
            rcd.append(p)
        return rcd

    def getcwd(self):
        return '/' + '/'.join(self.curdir)

    @staticmethod
    def showitems(itms, max_width = 60, tab_width = 6):
        rs = []
        line = ''
        for itm in itms:
            nline = line
            if nline:
                nline += '\t'
            nline += itm
            nline = nline.expandtabs(tab_width)
            if len(nline) > max_width:
                rs.append(line)
                line = itm
            else:
                line = nline
        if line:
            rs.append(line)
        return '\n'.join(rs)

    @staticmethod
    def gid2name(gid):
        return 'G{:03X}'.format(gid)

    @staticmethod
    def gname2id(gn):
        return int(gn[1:], 16) if gn[0] == 'G' else -1

    def getfiles(self, gname):
        gid = self.gname2id(gname)
        if not gid in self.groups or not 'files' in self.groups[gid]:
            print('group not exist:', gname)
            return None
        return self.groups[gid]['files']

    def ls(self, path = '.'):
        ddir = self.relpath(path)
        if len(ddir) == 0:
            itms = [self.gid2name(k) for k in self.groups.keys()]
            print(self.showitems(itms))
            return
        gfiles = self.getfiles(ddir[0])
        if not gfiles:
            return
        if len(ddir) == 1:
            itms = gfiles.keys()
            print(self.showitems(itms))
            return
        print('invalid path:', path)

    def pwd(self):
        print(self.getcwd())

    def cd(self, path):
        ddir = self.relpath(path)
        if len(ddir) > 1:
            print('invalid path:', path)
            return
        elif len(ddir) == 1:
            if not self.getfiles(ddir[0]):
                return
        self.curdir = ddir
        self.pwd()

    def getfile(self, ddir):
        if len(ddir) != 2:
            print('invalid path:', ddir)
        gname, fname = ddir
        gfiles = self.getfiles(gname)
        if not gfiles:
            return
        if not fname in gfiles:
            print('file not exist: {}/{}'.format(gname, fname))
            return
        fdesc = gfiles[fname]
        rraw = self.raw[fdesc['offset'] : fdesc['offset'] + fdesc['size']]
        return rraw, fdesc

    def cat(self, path):
        ddir = self.relpath(path)
        rraw, fdesc = self.getfile(ddir)
        return sp.data_pack(sp.desc_buf(len(rraw)), rraw)

    def foreach_file(self, hndl, ddir):
        rraw, fdesc = self.getfile(ddir)
        return hndl(rraw, fdesc, *ddir)

    def _foreach(self, hndl, ddir = [], silence = 2):
        if len(ddir) > 2:
            print('invalid path:', ddir)
        elif len(ddir) > 1:
            rs = self.foreach_file(hndl, ddir)
            if rs == '':
                rs = 'for file: {0[0]}/{0[1]}'.format(ddir)
            if rs and silence > 1:
                print(rs)
        elif len(ddir) > 0:
            gfiles = self.getfiles(ddir[0])
            if not gfiles:
                return
            if silence > 0:
                print('for group:', ddir[0])
            for fn in gfiles.keys():
                if fn == '__eof__':
                    continue
                self._foreach(hndl, ddir + [fn], silence)
        else:
            for gid in self.groups.keys():
                gn = self.gid2name(gid)
                self._foreach(hndl, ddir + [gn], silence)

    def foreach(self, hndl, path = '.', silence = 2):
        ddir = self.relpath(path)
        self._foreach(hndl, ddir, silence)

prog_header = sp.desc_pack(
    ('headlen', sp.desc_uword),
    ('tablen', sp.desc_uword),
    ('codelen', sp.desc_uint),
)

class c_prog_file:

    def __init__(self, raw):
        self.raw = raw
        self.pos = 0
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

    def scan(self):
        if self.scan_done:
            return True
        if not self.scan_header():
            return False
        if not self.scan_str():
            return False
        self.scan_done = True
        return True

    def scan_header(self):
        if self.pos > 0:
            return False
        dat = self.get_pack(prog_header)
        if dat['headlen'].value != 8:
            print('invalid prog header length:', dat['headlen'].value)
            return False
        self.strtab_pos = dat['tablen'].value
        self.data_pos = dat['codelen'].value
        segs = self.scan_tab(
            dat['tablen'].value - dat['headlen'].value, self.data_pos)
        if not segs:
            return False
        self.segs = segs
        strsegs = self.scan_tab(
            self.segs[0]['offset'] - self.strtab_pos, len(self.raw))
        if not strsegs:
            return False
        self.strsegs = strsegs
        for segdesc in self.segs:
            if not self.scan_seg(segdesc):
                return False
        return True

    def scan_str(self):
        if not self.strsegs:
            return True
        self.pos = self.strsegs[0]['offset']
        for strdesc in self.strsegs:
            if strdesc['size'] == 0:
                continue
            if not self.scan_dat(strdesc):
                return False
        return True

    def scan_tab(self, tablen, nxt_pos, offset = 0):
        if tablen % 2 or tablen == 0:
            print('invalid prog header tab length:', tablen)
            return None
        tabdesc = sp.desc_arr(int(tablen / 2), sp.desc_uword)
        dat = self.get_pack(tabdesc)
        segs = []
        last_seg = None
        for e in dat:
            ent = e.value + offset
            seg = {
                'offset': ent
            }
            if last_seg:
                last_seg['size'] = ent - last_seg['offset']
            last_seg = seg
            segs.append(seg)
        if not last_seg:
            print('prog should have at least 1 seg')
            return None
        last_seg['size'] = nxt_pos - last_seg['offset']
        return segs

    def scan_seg(self, segdesc):
        if self.pos != segdesc['offset']:
            print('invalid seg offset: 0x{:x}/0x{:x}'.format(
                self.pos, segdesc['offset']))
            return False
        dat = self.get_pack(sp.desc_buf(segdesc['size']))
        for i in range(0, len(dat), 2):
            if dat[i:i+2].value == b'\xff\xff':
                tablen = i
                break
        else:
            print('missing seg spliter')
            return False
        if tablen == 0:
            if len(dat) != 2:
                print('invalid seg head:', segdesc)
                return False
            else:
                return True
        self.pos = segdesc['offset']
        codesegs = self.scan_tab(
            tablen, segdesc['offset'] + segdesc['size'],
            offset = segdesc['offset'])
        if not codesegs:
            return False
        self.pos += 2
        if codesegs[0]['offset'] != self.pos:
            print('invalid 1st code: 0x{:x}/0x{:x}'.format(
                self.pos, codesegs[0]['offset']))
        segdesc['codes'] = codesegs
        for codedesc in codesegs:
            if not self.scan_dat(codedesc):
                return False
        return True

    def scan_dat(self, desc):
        if self.pos != desc['offset']:
            print('invalid dat offset: 0x{:x}/0x{:x}'.format(
                self.pos, desc['offset']))
            return False
        dat = self.get_pack(sp.desc_buf(desc['size']))
        desc['data'] = dat.buffer()
        return True

    def show_str(self, enc = 'shift-jis'):
        for strdesc in self.strsegs:
            print('text seg 0x{:x}'.format(strdesc['offset']))
            if strdesc['size'] == 0:
                continue
            print('length:', strdesc['size'])
            ppr(strdesc['data'].decode(enc, errors = 'ignore'))

    def show(self):
        self.show_str()

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

from find_sj_text import c_text_finder

def find_text_in_raw(raw, fdesc, gname, fname):
    finder = c_text_finder(raw)
    finder.scan()
    if len(finder.text_list) > 5:
        return ''
    else:
        return None

def unpack_hndl(sav_path, force = False):
    def save_file(raw, fdesc, gname, fname):
        if not force and find_text_in_raw(raw, fdesc, gname, fname) is None:
            return None
        if not os.path.exists(sav_path):
            os.mkdir(sav_path)
        dir_path = os.path.join(sav_path, gname)
        if not os.path.exists(dir_path):
            os.mkdir(dir_path)
        file_name = os.path.join(dir_path, fname)
        with open(file_name, 'wb') as fd:
            fd.write(raw)
        return 'unpack: {}/{} to {}'.format(gname, fname, file_name)
    return save_file

def cutstring(buf, enc = 'shift-jis', eos = b'\0', maxlen = 200):
    rlen = buf.find(eos)
    if rlen < 0:
        rlen = math.inf
    rlen = min(rlen, len(buf), maxlen)
    return buf[:rlen].decode(enc, errors = 'ignore')

def cutdat(dat, paddr, **kargs):
    addr = sp.data_pack(sp.desc_uword, dat[paddr:paddr+2]).value
    return cutstring(dat[addr:].value, **kargs)

def ptxt(dat, st, ed):
    ppr([(hex(i), cutdat(dat, i)) for i in range(st, ed, 2)])

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

    ext_path = r'G:\emu\ps\jpsxdec_v1-00_rev3921\extable\l3t1e1'
    mf = c_mic_file(raw)
    
    def upk():
        mf.scan()
        mf.foreach(unpack_hndl(ext_path))
        
    def gfile(gid):
        mf.scan()
        gn = mf.gid2name(gid) + '/PROG.BIN'
        return mf.cat(gn)

    def sprog(gid):
        gf = gfile(gid)
        pf = c_prog_file(gf)
        pf.scan()
        pf.show()
        return pf
