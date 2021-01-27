#! python3
# coding: utf-8

import os, os.path

HZK14_FILE = 'assets/HZK14'
HZK16_FILE = 'assets/HZK16'
PSBIOS_FILE = 'assets/SCPH1001.BIN'

HZK14_FILE = os.path.abspath(HZK14_FILE)
HZK16_FILE = os.path.abspath(HZK16_FILE)
PSBIOS_FILE = os.path.abspath(PSBIOS_FILE)

class c_charset_mapper:

    codec = None

    def map(self, hc, lc):
        return NotImplemented

    def unmap(self, idx):
        return NotImplemented

class c_gb2312_mapper(c_charset_mapper):

    codec = 'gb2312'

    @staticmethod
    def map(hc, lc):
        if hc < 0xa1 or not 0xa1 <= lc < 0xff:
            return None
        return (hc - 0xa1) * 0x5e + (lc - 0xa1)

    @staticmethod
    def unmap(idx):
        return int(idx / 0x5e) + 0xa1, (idx % 0x5e) + 0xa1

class c_psbios_sj_mapper(c_charset_mapper):

    codec = 'shift-jis'
    
    pb_sj_hole = [
        (0x81ad, 0x81b8),
        (0x81c0, 0x81c8),
        (0x81cf, 0x81da),
        (0x81e9, 0x81f0),
        (0x81f8, 0x81fc),
        (0x8240, 0x824f),
        (0x8259, 0x8260),
        (0x827a, 0x8281),
        (0x829b, 0x829f),
        (0x82f2, 0x8340),
        (0x8397, 0x839f),
        (0x83b7, 0x83bf),
        (0x83d7, 0x8440),
        (0x8461, 0x8470),
        (0x8492, 0x849f),
        (0x84bf, 0x889f),
    ]

    def __init__(self):
        super().__init__()
        self.pb_sj_hole = [
            tuple(
                self._map_nohole(v >> 8, v & 0xff) for v in vs
            ) for vs in self.pb_sj_hole
        ]

    @staticmethod
    def _map_nohole(hc, lc):
        if hc < 0x81 or not 0x40 <= lc < 0xfd or lc == 0x7f:
            return None
        r = (hc - 0x81) * 0xbc + (lc - 0x40)
        if lc > 0x7f:
            r -= 1
        return r

    @staticmethod
    def _unmap_nohole(idx):
        hc = int(idx / 0xbc) + 0x81
        lc = (idx % 0xbc) + 0x40
        if lc >= 0x7f:
            lc += 1
        return hc, lc
    
    def map(self, hc, lc):
        idx = self._map_nohole(hc, lc)
        if idx is None:
            return None
        ri = idx
        for st, ed in self.pb_sj_hole:
            if idx >= ed:
                ri -= ed - st
            elif idx >= st:
                return None
            else:
                break
        return ri

    def unmap(self, idx):
        for st, ed in self.pb_sj_hole:
            if idx >= st:
                idx += ed - st
        return self._unmap_nohole(idx)

class c_charset:

    def __init__(self, raw, size, wide, mapper, offset = 0):
        self.raw = raw
        self.chrsz = size
        self.wide = wide
        self.chrlen = int(size[0] * size[1] / 8 * wide)
        self.mapper = mapper
        self.offset = offset

    @property
    def codec(self):
        return self.mapper.codec

    def get_idx_by_code(self, c, rs = True):
        idx = self.mapper.map(*c)
        if not idx and rs:
            raise ValueError('invalid char')
        return idx

    def get_code_by_idx(self, idx):
        return bytes(self.mapper.unmap(idx))

    def get_offset_by_idx(self, idx):
        return idx * self.chrlen + self.offset

    def get_data_by_ofs(self, ofs):
        return self.raw[ofs:ofs+self.chrlen]

    def get_char_data(self, c):
        idx = self.get_idx_by_code(c)
        ofs = self.get_offset_by_idx(idx)
        return self.get_data_by_ofs(ofs)

    def copy_to(self, dset, schar, dchar = None, idx = 0):
        if not (self.wide == dset.wide and
                self.chrsz[0] == dset.chrsz[0]):
            raise ValueError('dest set not match')
        sdat = self.get_char_data(schar)
        if dchar:
            didx = dset.get_idx_by_code(dchar)
        else:
            didx = 0
        didx += idx
        if self.chrlen > dset.chrlen:
            sdat = sdat[:dset.chrlen]
        elif self.chrlen < dset.chrlen:
            sdat += b'\00' * (dset.chrlen - self.chrlen)
        dofs = dset.get_offset_by_idx(didx)
        dnofs = dofs + len(sdat)
        if dnofs > len(dset.raw):
            raise RuntimeError('charset overflow')
        #print('set', hex(dofs), hex(dnofs))
        dset.raw = dset.raw[:dofs] + sdat + dset.raw[dnofs:]
        return dset.get_code_by_idx(didx)

    def write_file(self, fn):
        with open(fn, 'wb') as fd:
            fd.write(self.raw)

class c_charset_filler:

    def __init__(self, src_set, dst_set, start_char):
        self.src_set = src_set
        self.dst_set = dst_set
        try:
            self.st_char = start_char.encode(self.dst_set.codec)
            self.cur_idx = self.dst_set.get_idx_by_code(self.st_char)
        except:
            raise ValueError('invalid start char: ' + start_char)
        self.map = {}

    def emit(self, char):
        if char in self.map:
            ci = self.map[char]
            ci['num'] += 1
            return ci['code']
        try:
            cc = char.encode(self.dst_set.codec)
            idx = self.dst_set.get_idx_by_code(cc)
        except:
            pass
        else:
            if idx < self.cur_idx:
                self.map[char] = {
                    'code': cc,
                    'num': 1,
                }
                return cc
        try:
            cc = char.encode(self.src_set.codec)
            idx = self.src_set.get_idx_by_code(cc)
        except:
            raise ValueError('invalid char: ' + char)
        cc = self.src_set.copy_to(self.dst_set, cc, idx = self.cur_idx)
        self.cur_idx += 1
        self.map[char] = {
            'code': cc,
            'num': 1,
        }
        return cc

    def save_set(self, fn):
        self.dst_set.write_file(fn)

def std_filler(sfn = HZK14_FILE, dfn = PSBIOS_FILE):
    with open(HZK14_FILE, 'rb') as sfd:
        with open(PSBIOS_FILE, 'rb') as dfd:
            filler = c_charset_filler(
                c_charset(sfd.read(), [8, 14], 2, c_gb2312_mapper()),
                c_charset(dfd.read(), [8, 15], 2,
                          c_psbios_sj_mapper(), 0x66000),
                '亜')
    return filler

if __name__ == '__main__':

    DST_PB_FILE = r'G:\emu\ps\no$psx\PSX-BIOS.ROM'

    def main1():
        cs_filler = std_filler()
        def sav():
            cs_filler.save_set(DST_PB_FILE)
        cs_filler.sav = sav
        return cs_filler
    cs_filler = main1()

    
