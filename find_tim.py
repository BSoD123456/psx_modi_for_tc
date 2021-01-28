#! python3
# coding: utf-8

import os, os.path
import math
import json

import stat_parser as sp

tim_header = sp.desc_pack(
    ('magic', sp.desc_uint),
    ('flags', sp.desc_uint),
)

tim_body_header = sp.desc_pack(
    ('length', sp.desc_uint),
    ('ori_x', sp.desc_uword),
    ('ori_y', sp.desc_uword),
    ('width', sp.desc_uword),
    ('height', sp.desc_uword),
)

unknown_uint = sp.desc_uint

class c_tim_scanner:

    
    TIM_MAGIC = b'\x10\x00\x00\x00'

    def __init__(self, raw, offset = 0,
                 base_sect = 0, sector_size = 2048):
        self.raw = raw
        self.pos = offset
        self.base_sect = base_sect
        self.sector_size = sector_size
        self.tim_files = []
        self.unknown_files = []

##    def get_sector(self):
##        rawlen = len(self.raw)
##        if self.pos >= rawlen:
##            return None
##        stpos = self.pos
##        edpos = stpos + self.sector_size
##        rmlen = 0
##        if edpos > rawlen:
##            rmlen = edpos - rawlen
##            edpos = rawlen
##        sect = self.raw[stpos:edpos]
##        if rmlen > 0:
##            sect = sect + b'\00' * rmlen
##        return sect

    def sector_num(self, addr):
        return math.floor(addr / self.sector_size) + self.base_sect

    def valid_flags(self, fval):
        return ((fval & (0x100000000 - 0xc)) == 0 and
                fval != 0 and fval != 10 and fval != 11 and fval != 12)

    def goto_next_sector(self):
        self.pos = (
            math.floor(self.pos / self.sector_size) + 1) * self.sector_size

    def get_pack(self, desc, noshift = False):
        if self.pos >= len(self.raw):
            return None
        spos = self.pos
        dpos = spos + len(desc)
        if not noshift:
            self.pos = dpos
        #print('->', hex(spos))
        return sp.data_pack(desc,
                            self.raw[spos:dpos])

    def find_next_tim(self):
        while self.pos <= len(self.raw) - len(tim_header):
            head = self.get_pack(tim_header, True)
            if head['magic'].value == 0x10:
                if self.valid_flags(head['flags'].value):
                    self.pos -= 4
                    print('tim found', hex(self.pos))
                    return True
            self.pos += 2
        else:
            self.pos = len(self.raw)
            print('done')
            return False

    def scan_body(self):
        head = self.get_pack(tim_body_header)
        if not head:
            return 0
        if not head['length'].value - 12 == (
            head['width'].value * head['height'].value * 2):
            print('invalid body:',
                  head['length'].value - 12,
                  head['width'].value,
                  head['height'].value,
                  head['width'].value * head['height'].value * 2)
            return 0
        self.pos += head['length'].value - len(head)
        return head['length'].value

    def repr_ukint(self, ukint):
        if isinstance(ukint.value, list):
            rval = 0
            for v in ukint.value:
                rval <<= 16
                rval += v.value
        else:
            rval = ukint.value
        return ('{:0' + str(len(ukint) * 2) + 'x}').format(rval)

    def find_next(self, start_pos, ukint):
        if (len(self.unknown_files) > 0 and
            not self.unknown_files[-1]['done']):
            ukfile = self.unknown_files[-1]
        else:
            ukfile = {
                'ukint': self.repr_ukint(ukint),
                'offset': start_pos,
                'done': False,
            }
            self.unknown_files.append(ukfile)
        self.pos = start_pos + 2
        found = self.find_next_tim()
        ukfile['size'] = self.pos - ukfile['offset']
        print('file:', hex(ukfile['offset']), hex(ukfile['size']))
        return found

    def scan_next(self, last_ukint = None):
        if last_ukint:
            ukint = last_ukint
        else:
            ukint = self.get_pack(unknown_uint)
        if not ukint:
            print('done')
            return False
        print('===', self.repr_ukint(ukint), '===')
        print('scan:', hex(self.pos), 'in sect', self.sector_num(self.pos))
        start_pos = self.pos
        head = self.get_pack(tim_header)
        if not head:
            print('done')
            return False
        if head['magic'].value == 0xffffffff:
            print('sector done')
            self.goto_next_sector()
            return True
        elif (head['magic'].value != 0x10 or
              not self.valid_flags(head['flags'].value)):
            retry_for_uki = True
            if not last_ukint is None:
                retry_for_uki = False
            elif ukint.value == 0x10:
                self.pos -= 4 + len(head)
                pad_ukint = self.get_pack(sp.desc_void)
            elif ukint.value == 0x100000:
                self.pos -= 4 + len(head)
                pad_ukint = self.get_pack(sp.desc_uword)
            elif (head['magic'].value >> 16) == 0x10:
                self.pos -= 4+ len(head)
                pad_ukint = self.get_pack(sp.desc_arr(3, sp.desc_uword))
            else:
                retry_for_uki = False
            if retry_for_uki:
                print('retry for no ukint')
                return self.scan_next(pad_ukint)
            if last_ukint:
                self.pos -= len(head)
                return self.scan_next(False)
            print('unknown header: ', end = '')
            print(head['magic'].buffer())
            found = self.find_next(start_pos, ukint)
            if not found:
                return False
            else:
                return True
        else:
            print('tim', head['flags'].value)
        has_clut = (head['flags'].value & 8)
        if has_clut:
            blen = self.scan_body()
            if not blen:
                found = self.find_next(start_pos, ukint)
                if not found:
                    return False
                else:
                    return True
            print('  clut:', hex(blen))
        blen = self.scan_body()
        if not blen:
            found = self.find_next(start_pos, ukint)
            if not found:
                return False
            else:
                return True
        print('  body:', hex(blen))
        self.tim_files.append({
            'ukint': self.repr_ukint(ukint),
            'offset': start_pos,
            'size': self.pos - start_pos,
        })
        if len(self.unknown_files) > 0:
            self.unknown_files[-1]['done'] = True
        return True

    def scan(self):
        while self.scan_next():
            pass

    def show_files(self, flist):
        for fi in flist:
            print('===', fi['ukint'], '===')
            print('sec:', self.sector_num(fi['offset']),
                  '-', self.sector_num(fi['offset'] + fi['size'] - 1),
                  'offset:', hex(fi['offset']),
                  'size:', hex(fi['size']),
                  'header:', self.raw[fi['offset']:fi['offset']+4])

    def show_ukfiles(self):
        self.show_files(self.unknown_files)

    def show_timfiles(self):
        self.show_files(self.tim_files)

    def iter_ukraw(self):
        tag_patt = '{:08x}_{:s}'
        for fi in self.unknown_files:
            tag = tag_patt.format(fi['offset'], fi['ukint'])
            yield self.raw[fi['offset']:fi['offset']+fi['size']], tag

    def save_scan(self, sav_fn):
        with open(sav_fn, 'w') as fd:
            json.dump({
                'tim': self.tim_files,
                'unknown': self.unknown_files,
            }, fd)

    def load_scan(self, sav_fn):
        try:
            with open(sav_fn, 'r') as fd:
                rs = json.load(fd)
                self.tim_files = rs['tim']
                self.unknown_files = rs['unknown']
        except:
            self.scan()
            self.save_scan(sav_fn)

    def save_files(self, ext_dir, force = False, target = []):
        if not os.path.exists(ext_dir):
            os.makedirs(ext_dir)
        fn_patt = '{:08x}_{:s}.{:s}'
        saved = False
        if not target or 'tim' in target:
            saving_dialog = 'saving tim filse ...'
            for fi in self.tim_files:
                fn = os.path.join(
                    ext_dir, fn_patt.format(fi['offset'], fi['ukint'], 'tim'))
                if not force and os.path.exists(fn):
                    continue
                if saving_dialog:
                    print(saving_dialog)
                    saving_dialog = None
                    saved = True
                with open(fn, 'wb') as fd:
                    fd.write(self.raw[fi['offset']:fi['offset']+fi['size']])
        if not target or 'ext' in target:
            saving_dialog = 'saving unknown filse ...'
            for fi in self.unknown_files:
                fn = os.path.join(
                    ext_dir, fn_patt.format(fi['offset'], fi['ukint'], 'uk'))
                if not force and os.path.exists(fn):
                    continue
                if saving_dialog:
                    print(saving_dialog)
                    saving_dialog = None
                    saved = True
                with open(fn, 'wb') as fd:
                    fd.write(self.raw[fi['offset']:fi['offset']+fi['size']])
        if saved:
            print('done')

    def import_file(self, fname, raw):
        try:
            tag, typ = fname.split('.')
            ofs, ukint = tag.split('_')
            ofs = int(ofs, 16)
        except:
            print('invalid file name: ' + fname)
            return False
        if typ == 'tim':
            flist = self.tim_files
        elif ename == 'uk':
            typ = self.unknown_files
        else:
            print('invalid file type: ' + typ)
            return False
        for fi in flist:
            lraw = len(raw)
            if fi['offset'] == ofs:
                if fi['size'] > lraw:
                    raw += b'\00' * lraw
                elif fi['size'] < lraw:
                    print('file too big: ' + str(lraw) + '/' + str(fi['size']))
                    return False
                break
            elif fi['offset'] > ofs:
                print('invalid offset: ' + hex(ofs))
                return False
        else:
            print('invalid offset: ' + hex(ofs))
            return False
        self.raw = self.raw[:ofs] + raw + self.raw[ofs+len(raw):]
        return True

if __name__ == '__main__':
    
    work_path = r'G:\emu\ps\jpsxdec_v1-00_rev3921\extable\tc1'
    dest_file = 'DATA.BIN'

    sav_file = 'timscan.json'
    with open(os.path.join(work_path, dest_file), 'rb') as fd:
        scanner = c_tim_scanner(fd.read(), base_sect = 422)
    scanner.load_scan(os.path.join(work_path, sav_file))

    def extract(force = False):
        ext_dir = os.path.join(work_path, dest_file + '.ext')
        scanner.save_files(ext_dir, force)
    

    
    
