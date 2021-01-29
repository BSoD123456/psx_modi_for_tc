#! python3
# coding: utf-8

try:
    from PIL import Image
except:
    print('''
please install Pillow first.
for windows use:
py -3 -m pip install pillow
for others use:
python -m pip install pillow
''')
    raise

import stat_parser as sp
from find_tim import tim_header, tim_body_header

class c_tim_converter:

    def __init__(self, raw):
        self.raw = raw
        self.pos = 0
        self.parse_header()
        self.parse_body_image()
        self.parse_body_clut()
        self.make_image()

    def get_datapack(self, desc):
        epos = self.pos + len(desc)
        rdat = self.raw[self.pos:epos]
        dp = sp.data_pack(desc, rdat)
        self.pos = epos
        return dp

    def parse_body_header(self, bofs = False):
        hd = self.get_datapack(tim_body_header)
        hlen = hd['length'].value - len(hd)
        hw = hd['width'].value
        hh = hd['height'].value
        if not hlen == hw * hh * 2:
            raise ValueError('invalid body header')
        elif hlen == 0:
            raise ValueError('empty body')
        body_desc = sp.desc_arr(
            hh, sp.desc_arr(hw, sp.desc_uword))
        if bofs:
            offset = self.pos
        bd = self.get_datapack(body_desc)
        if bofs:
            return bd, offset
        else:
            return bd

    def parse_header(self):
        self.header = self.get_datapack(tim_header)
        hflags = self.header['flags'].value
        if not (self.header['magic'].value == 0x10 and
                (hflags & (0xffffffff ^ 0xb)) == 0):
            raise ValueError('invalid header')
        self.has_clut = (hflags & 0x8)
        self.bpp = (hflags & 0x3)
        if self.has_clut:
            if self.bpp == 3:
                raise ValueError('invalid header type')
            self.clut = self.parse_body_header()
        self.body, self.body_offset = self.parse_body_header(True)

    def parse_body_image(self):
        rows = len(self.body.value)
        rowlen = len(self.body[0].value)
        self.height = rows
        if self.bpp in [0, 1]:
            row_desc = sp.desc_pack(
                ('row', sp.desc_arr(rowlen * 2, sp.desc_ubyte)))
            self.width = ((rowlen * 4) >> self.bpp)
        elif self.bpp == 2:
            row_desc = sp.desc_pack(
                ('row', sp.desc_arr(rowlen, sp.desc_uword)))
            self.width = rowlen
        elif self.bpp == 3:
            padlen = (rowlen * 2) % 3
            self.width = int(rowlen / 2)
            if padlen == 0:
                pad_desc = sp.desc_void
            elif padlen == 1:
                pad_desc = sp.desc_ubyte
            elif padlen == 1:
                pad_desc = sp.desc_uword
            row_desc = sp.desc_pack(
                ('row', sp.desc_arr(self.width,
                                    sp.desc_arr(3, sp.desc_ubyte))),
                ('pad', pad_desc))
        body_desc = sp.desc_arr(rows, row_desc)
        self.body = sp.data_pack(body_desc, self.body.buffer())

    def parse_body_clut(self):
        if not self.has_clut:
            return
        body_desc = sp.desc_arr(int(len(self.clut) / 2), sp.desc_uword)
        self.clut = sp.data_pack(body_desc, self.clut.buffer())
        self.clut = [i.value for i in self.clut]
        self.clut_rev = {}
        for i in range(len(self.clut) - 1, -1, -1):
            self.clut_rev[self.clut[i]] = i

    def get_body_value(self, x, y):
        rx = x
        if self.bpp == 0:
            rx = int(x / 2)
            rxb = x % 2
        v = self.body[y]['row'][rx].value
        if self.bpp == 0:
            if rxb:
                v >>= 4
            else:
                v &= 0xf
        return v

    def set_body_value(self, x, y, v):
        rx = x
        if self.bpp == 0:
            rx = int(x / 2)
            ov = self.body[y]['row'][rx].value
            if x % 2:
                v = (v << 4) & 0xf0
                ov &= 0xf
            else:
                v &= 0xf
                ov &= 0xf0
            v = (ov | v)
        if self.bpp == 3:
            self.body[y]['row'][rx][0].value = v[0]
            self.body[y]['row'][rx][1].value = v[1]
            self.body[y]['row'][rx][2].value = v[2]
        else:
            self.body[y]['row'][rx].value = v

    def get_rgba_by_value(self, v, bpp = None):
        if bpp is None:
            bpp = self.bpp
        bpv = (4 << bpp)
        bpvi = int(bpv / 3)
        if bpp == 3:
            return (*(i.value for i in v), False)
        else:
            stp = ((v >> (bpv - 1)) & 1)
            rgb = tuple(
                (v >> (i * bpvi)) & ((1 << bpvi) - 1)
                for i in range(3))
        # for black
        if rgb == (0, 0, 0):
            stp = not stp
        else:
            stp = not not stp
        return (*(vi << (8 - bpvi) for vi in rgb), stp)

    def get_value_by_rgba(self, rgba, bpp = None):
        if bpp is None:
            bpp = self.bpp
        if bpp == 3:
            return rgba
        v = 0
        bpv = (4 << bpp)
        bpvi = int(bpv / 3)
        for i in range(2, -1, -1):
            v = (v << bpvi) + ((rgba[i] >> (8 - bpvi)) & ((1 << bpvi) - 1))
        stp = rgba[3]
        if v == 0:
            stp = not stp
        if stp:
            v |= (1 << (bpv - 1))
        else:
            v &= (1 << (bpv - 1)) - 1
        return v

    def get_clut_value(self, ofs):
        if not self.has_clut:
            raise ValueError('no clut')
        v = self.clut[ofs]
        return self.get_rgba_by_value(v, 2)

    def find_clut_value(self, rgba):
        if not self.has_clut:
            raise ValueError('no clut')
        best_match = (float('inf'), None)
        for i, v in enumerate(self.clut):
            vrgba = self.get_rgba_by_value(v, 2)
            if not vrgba[3] == rgba[3]:
                continue
            dist = (abs(rgba[0] - vrgba[0]) +
                    abs(rgba[1] - vrgba[1]) +
                    abs(rgba[2] - vrgba[2]))
            if dist < best_match[0]:
                best_match = (dist, i)
            if dist == 0:
                break
        v = best_match[1]
        if v is None:
            raise ValueError('no match for clut')
        return v

    def get_rgba(self, x, y):
        v = self.get_body_value(x, y)
        if self.has_clut:
            return self.get_clut_value(v)
        else:
            return self.get_rgba_by_value(v)

    def set_rgba(self, x, y, rgba):
        if self.has_clut:
            vi = self.get_value_by_rgba(rgba, 2)
            if vi in self.clut_rev:
                v = self.clut_rev[vi]
            else:
                v = self.find_clut_value(rgba)
                self.clut_rev[vi] = v
        else:
            v = self.get_value_by_rgba(rgba)
        self.set_body_value(x, y, v)

    def iter_rgba(self):
        for y in range(self.height):
            for x in range(self.width):
                rgba = self.get_rgba(x, y)
                yield rgba, x, y

    def make_image(self):
        self.image = Image.new(
            mode = 'RGBA', size = (self.width, self.height))
        px = self.image.load()
        for rgba, x, y in self.iter_rgba():
            alpha = 0 if rgba[3] else 255
            px[x, y] = (rgba[0], rgba[1], rgba[2], alpha)

    def import_raw(self):
        img_dat = self.body.buffer()
        sofs = self.body_offset
        eofs = sofs + len(img_dat)
        self.raw = self.raw[:sofs] + img_dat + self.raw[eofs:]

    def import_image(self):
        px = self.image.load()
        for y in range(self.image.height):
            for x in range(self.image.width):
                rgba = px[x, y]
                self.set_rgba(x, y,
                    (rgba[0], rgba[1], rgba[2], rgba[3] < 128))
        self.import_raw()

    def save_png(self, png_fn):
        self.image.save(png_fn, 'png')

    def load_png(self, png_fn):
        self.image = Image.open(png_fn).convert('RGBA')
        self.import_image()
    
if __name__ == '__main__':

    tim_file = r'table\ext\tim\005aa270_000049c4.tim'
    d_tim_file = r'table\sav\tim\cnv_005aa270_000049c4.tim'
    d_png_file = r'table\sav\tim\cnv_005aa270_000049c4.png'

    def main():
        with open(tim_file, 'rb') as fd:
            tim = c_tim_converter(fd.read())
        def save():
            tim.import_image()        
            with open(d_tim_file, 'wb') as fd:
                fd.write(tim.raw)
        tim.save = save
        return tim
    tim = main()
    
