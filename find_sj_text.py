#! python3
# coding: utf-8

#[0x40~0xfc]
shift_jis_valid_page = [
    [0x81, 0, 0],
    [0x82, 0x4f, 0xf2],
    [0x83, 0, 0xd6],
    [0x84, 0, 0xbe],
    [0x88, 0x9f, 0],
    (0x89, 0x98),
    [0x98, 0, 0x73],
]
def _complete_sjvp(tab):
    lopage = [0x40, 0xfd]
    rtab = []
    for itm in tab:
        if isinstance(itm, tuple):
            for i in range(itm[0], itm[1]):
                rtab.append([i, *lopage])
        else:
            if not itm[1]:
                itm[1] = lopage[0]
            if not itm[2]:
                itm[2] = lopage[1]
            rtab.append(itm)
    return rtab
shift_jis_valid_page = _complete_sjvp(shift_jis_valid_page)

def dec_shift_jis(byt):
    assert len(byt) == 2
    try:
        s = byt.decode('shift-jis')
    except:
        s = 'decode error'
    v = list(byt)
    #v = v[0] * 0x100 + v[1]
    return s, v

def valid_shift_jis_val(v):
    for itm in shift_jis_valid_page:
        if v[0] == itm[0] and itm[1] <= v[1] < itm[2]:
            return True
    return False

def invalid_spec_text(s):
    if len(s) != 4:
        return False
    ss0 = s[0] * 0x100 + s[1]
    ss1 = s[2] * 0x100 + s[3]
    if ((s[0] < 0x88 and s[2] >= 0x88) or
        (ss0 < 0x829f and ss1 < 0x829f) or
        0x839f <= ss0 < 0x889f or
        0x839f <= ss1 < 0x889f or
        ss0 == ss1 > 0x889f
        ):
        return True

def invalid_spec_text_trimed(s):
    if len(s) != 4:
        return False
    if ((s[0] < 0x88 and s[2] < 0x88) or
        (s[0] >= 0x88 and s[2] >= 0x88)
        ):
        return True

def trim_invalid_head(s):
    for i in range(len(s)):
        if 0x81 <= s[i] < 0x85 or 0x88 <= s[i] < 0x99:
            return i
    return None

def valid_shift_jis_text(s):
    #print('check', len(s))
    last_at = False
    if s[-1] == 0x40: #b'@'
        s = s[:-1]
        last_at = True
    thp = trim_invalid_head(s)
    if thp is None:
        return None, None
    elif thp > 0:
        s = s[thp:]
        if invalid_spec_text_trimed(s):
            return None, None
    if len(s) % 2 or len(s) < 4:
        return None, None
    if invalid_spec_text(s):
        return None, None
    rs = ''
    for i in range(0, len(s), 2):
        c = s[i:i+2]
        rc, rv = dec_shift_jis(c)
        if not valid_shift_jis_val(rv):
            return None, None
        rs = rs + rc
    if last_at:
        rs += '@'
    #if invalid_spec_text(s):
    #    print('exclude', rs)
    return rs, thp

EOS = 0 #b'\00'
class c_text_finder:

    def __init__(self, raw, offset = 0,
                 checker = valid_shift_jis_text):
        self.raw = raw
        self.pos = offset
        self.checker = valid_shift_jis_text
        self.text_list = []

    def goto_next_string(self):
        if self.pos >= len(self.raw):
            return False
        while self.raw[self.pos] == EOS:
            self.pos += 1
            if self.pos >= len(self.raw):
                return False
        return True

    def get_string_info(self):
        if not self.goto_next_string():
            return None, None, None
        start_pos = self.pos
        while self.raw[self.pos] != EOS:
            self.pos += 1
            if self.pos >= len(self.raw):
                return start_pos, self.pos, self.pos
        end_pos = self.pos
        self.goto_next_string()
        return start_pos, end_pos, self.pos

    def find_string(self):
        start_pos, end_pos, next_pos = self.get_string_info()
        if start_pos is None:
            return False
        src_s = self.raw[start_pos:end_pos]
        dst_s, trim_pos = self.checker(src_s)
        if dst_s:
            start_pos += trim_pos
            self.text_list.append({
                'text': dst_s,
                'info': (start_pos, end_pos - start_pos, next_pos - end_pos),
                'trans': '',
            })
            print('txt:', dst_s)
        return True

    def scan(self):
        while self.find_string():
            pass

    @staticmethod
    def valid_trans(txt_itm, chk_at = True):
        if not txt_itm['trans']:
            return None, None
        src = txt_itm['text']
        trans = txt_itm['trans']
        if chk_at and (src[-1] == '@') != (
            trans[-1] == '@'):
            raise ValueError('missed @ symbol')
        slen = len(src.encode('utf-8'))
        dlen = len(trans.encode('utf-8'))
        if slen + txt_itm['info'][2] - 1 < dlen:
            raise ValueError('trans too long')
        elif dlen < slen:
            trans += '\00' * (slen - dlen)
        return trans, txt_itm['info'][0]

if __name__ == '__main__':
    pass


