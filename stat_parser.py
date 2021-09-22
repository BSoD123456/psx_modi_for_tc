#! python3
# coding: utf-8

import math
from collections import OrderedDict
from pprint import pprint
import codecs

ENDIAN = 'LE'

class c_desc:

    def __init__(self):
        self.lazy_props = {}

    @staticmethod
    def lazy(hndl):
        name = hndl.__name__
        def _lzmethod(self, *args, **kargs):
            if not name in self.lazy_props:
                self.lazy_props[name] = hndl(self, *args, **kargs)
            return self.lazy_props[name]
        return _lzmethod

    @staticmethod
    def getbuf(raw, offset, length):
        return raw[offset: offset + length]

    def placein(self, val, container, offset):
        if container:
            val = container(self, val, offset)
        return val

    @staticmethod
    def placeout(val):
        if hasattr(val, 'value'):
            val = val.value
        return val

    def __len__(self):
        return NotImplemented

    def value(self, raw, offset = 0, container = None):
        return NotImplemented

    def buffer(self, buf):
        return bytes(buf)

    def show(self, val):
        if hasattr(val, 'show'):
            return val.show()
        else:
            return str(val)

class c_desc_void(c_desc):

    def __len__(self):
        return 0

    def value(self, raw, offset = 0, container = None):
        return self.placein(0, container, offset)

    def buffer(self, buf):
        return b''

    def show(self, val):
        return 'void'

class c_desc_int_le(c_desc):

    def __init__(self, length, signed = False):
        super().__init__()
        self.length = length
        self.signed = signed

    def __len__(self):
        return self.length
            
    @staticmethod
    def numbytes(val):
        return int(math.log(val, 2) / 8) + 1 if val > 0 else 0

    def buf2num(self, buf):
        val = 0
        for i, v in enumerate(buf):
            val += (v << (i * 8))
        return val

    def num2arr(self, val):
        arr = []
        for i in range(self.numbytes(val)):
            arr.append((val & (0xff << (8 * i))) >> (8 * i))
        padlen = self.length - len(arr)
        if padlen > 0:
            arr = arr + [0] * padlen
        elif padlen < 0:
            arr = arr[:self.length]
        return arr

    def value(self, raw, offset = 0, container = None):
        buf = self.getbuf(raw, offset, self.length)
        val = self.buf2num(buf)
        sbit = (1 << (self.length * 8 - 1))
        if self.signed and (val & sbit):
            val -= (sbit << 1)
        return self.placein(val, container, offset)

    def buffer(self, val):
        val = self.placeout(val)
        return super().buffer(self.num2arr(val))

    def show(self, val):
        return hex(val)

class c_desc_int_be(c_desc_int_le):

    def buf2num(self, buf):
        val = 0
        for v in buf:
            val = (val << 8) + v
        return val

    def num2arr(self, val):
        arr = []
        bs = self.numbytes(val)
        for i in range(bs):
            i = bs - i - 1
            arr.append((val & (0xff << (8 * i))) >> (8 * i))
        padlen = self.length - len(arr)
        if padlen > 0:
            arr = [0] * padlen + arr
        elif padlen < 0:
            arr = arr[-self.length:]
        return arr

vbuf_to_str = lambda s: ''.join(chr(c) for c in s)
codecs.register_error('replace_with_bar',
    lambda e: (vbuf_to_str(e.object), e.start + 1))
class c_desc_buf(c_desc):

    def __init__(self, length, base = 0):
        super().__init__()
        self.length = length
        self.base = base

    def __len__(self):
        return self.length

    def getslice(self, st, ed):
        return c_desc_buf(ed - st, st)

    def value(self, raw, offset = 0, container = None):
        buf = self.getbuf(raw, offset, self.length)
        return self.placein(buf, container, offset)

    def buffer(self, buf):
        buf = self.placeout(buf)
        return super().buffer(buf)

    def show(self, buf, brief = 0x80):
        lb = len(buf)
        ellipsis = False
        if brief and lb > brief:
            ellipsis = True
            lb = min(lb, brief)
        rs = []
        for i in range(0, lb, 8):
            line_d1 = []
            line_s1 = []
            for j1 in range(2):
                line_d2 = []
                line_s2 = b''
                for j2 in range(4):
                    idx = i + j1 * 4 + j2
                    if idx >= lb:
                        break
                    val = buf[idx]
                    line_d2.append('{:02x}'.format(val))
                    line_s2 += bytes([val])
                line_d1.append(' '.join(line_d2))
                if line_s2:
                    line_s1.append(
                        #line_s2.decode('ascii', errors = 'replace_with_bar'))
                        vbuf_to_str(line_s2))
            rs.append('{:08x}: {: <11s} | {: <11s}   {}'.format(
                i + self.base, line_d1[0], line_d1[1], ' '.join(line_s1)))
        if ellipsis:
            rs.append('......')
        return rs

class c_desc_arr(c_desc):

    def __init__(self, length, subdesc):
        super().__init__()
        self.length = length
        self.subdesc = subdesc

    @c_desc.lazy
    def __len__(self):
        return len(self.subdesc) * self.length

    def value(self, raw, offset = 0, container = None):
        arr = []
        pos = offset
        step = len(self.subdesc)
        for i in range(self.length):
            arr.append(self.subdesc.value(raw, pos, container))
            pos += step
        return self.placein(arr, container, offset)

    def buffer(self, arr):
        arr = self.placeout(arr)
        buf = b''
        for i in range(self.length):
            val = arr[i]
            buf += self.subdesc.buffer(val)
        return buf

    def show(self, val):
        sup = super()
        return [sup.show(v) for v in val]

class c_desc_pack(c_desc):

    def __init__(self, *items):
        super().__init__()
        self.items = OrderedDict(items)

    @c_desc.lazy
    def __len__(self):
        return sum(len(desc) for desc in self.items.values())

    def __getitem__(self, key):
        return self.items[key]

    def value(self, raw, offset = 0, container = None):
        pack = OrderedDict()
        pos = offset
        for key, desc in self.items.items():
            pack[key] = desc.value(raw, pos, container)
            pos += len(desc)
        return self.placein(pack, container, offset)

    def buffer(self, pack):
        pack = self.placeout(pack)
        buf = b''
        for key, val in pack.items():
            desc = self.items[key]
            buf += desc.buffer(val)
        return buf

    def show(self, val):
        sup = super()
        return [(k, sup.show(v)) for k, v in val.items()]

desc_void = c_desc_void()
if ENDIAN == 'LE':
    c_desc_int = c_desc_int_le
elif ENDIAN == 'BE':
    c_desc_int = c_desc_int_be
desc_ubyte = c_desc_int(1)
desc_byte = c_desc_int(1, True)
desc_uword = c_desc_int(2)
desc_word = c_desc_int(2, True)
desc_uint = c_desc_int(4)
desc_int = c_desc_int(4, True)
desc_ulong = c_desc_int(8)
desc_long = c_desc_int(8, True)
desc_enum = desc_float = desc_pointer = desc_uint
desc_buf = c_desc_buf
desc_arr = c_desc_arr
desc_pack = c_desc_pack

class c_data:

    def __init__(self, desc, val = None, offset = 0):
        self.desc = desc
        self.value = val
        self.offset = offset

    def __bool__(self):
        return True

    def __len__(self):
        return len(self.desc)

    def __getitem__(self, key):
        if isinstance(key, slice) and hasattr(self.desc, 'getslice'):
            st = key.start
            if st is None:
                st = 0
            ed = key.stop
            if ed is None:
                ed = len(self)
            slcdesc = self.desc.getslice(st, ed)
            return slcdesc.value(self.buffer(), st, c_data)
        return self.value[key]

    def buffer(self):
        return self.desc.buffer(self.value)

    def show(self, *args, **kargs) :
        return self.desc.show(self.value, *args, **kargs)

def data_pack(desc, raw = None):
    if raw is None:
        raw = bytes(len(desc))
    elif len(raw) != len(desc):
        raise ValueError('desc length not match: {}/{}'.format(
            len(raw), len(desc)))
    return desc.value(raw, 0, c_data)

def data_update(dat, val):
    if type(val) is dict:
        for k in val:
            data_update(dat[k], val[k])
    elif type(val) is list:
        for i, v in enumerate(val):
            data_update(dat[i], v)
    else:
        dat.value = val
def show(data, *args, **kargs):
    pprint(data.show(*args, **kargs))


