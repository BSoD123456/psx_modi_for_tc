#! python3
# coding: utf-8

from mod_charset import c_psbios_sj_mapper, is_ascii

shift_jis_mapper = c_psbios_sj_mapper()

def valid_shift_jis_val(v):
    return not (shift_jis_mapper.map(*v) is None)

def valid_ctr_sym_val(v):
    return v.isdigit() or v == b'@' or v == b' '

def valid_ctr_sym_in_string(s):
    for c in s:
        ec = c.encode('utf-8')
        if len(ec) == 1 and not (c.isdigit() or c == '@'):
            return False
    return True

def invalid_spec_text(s, p):
    if len(s) - p != 4:
        return False
    ss0 = s[p] * 0x100 + s[p + 1]
    ss1 = s[p + 2] * 0x100 + s[p + 3]
    if ((s[p] < 0x88 and s[p + 2] >= 0x88) or
        (ss0 < 0x829f and ss1 < 0x829f) or
        0x839f <= ss0 < 0x889f or
        0x839f <= ss1 < 0x889f or
        ss0 == ss1 >= 0x889f or
        0x839f <= ss0 < 0x849f or
        0x839f <= ss1 < 0x849f
        ):
        return True
    return False

def invalid_spec_text_trimed(s, p):
    if len(s) - p != 4:
        return False
    ss0 = s[p] * 0x100 + s[p + 1]
    ss1 = s[p + 2] * 0x100 + s[p + 3]
    if ((s[p] < 0x88 and s[p + 2] < 0x88) or
        (s[p] >= 0x88 and s[p + 2] >= 0x88) or
        (ss0 < 0x889f and ss1 >= 0x889f)
        ):
        return True
    return False

def invalid_spec_text_spaced(rs):
    if len(rs) == 3 and rs[1:] == ' レ':
        return True
    return False

invalid_spec_list = set([
    '荒Ｒ',
    '煮苗44',
    '神弛3',
    '斜磁40',
    '式隠4 ',
])

def get_valid_char(s, p):
    l = len(s)
    if p >= l:
        return None, 0
    c = s[p:p+1]
    #if is_ascii(c[0]):
    if valid_ctr_sym_val(c):
        return c, 1
    if p > l - 2:
        return None, 1
    c = s[p:p+2]
    if valid_shift_jis_val(c):
        return c, 2
    return None, 1

def trim_invalid_head(s, p):
    i = p
    while i < len(s):
        c, step = get_valid_char(s, i)
        if not c is None:
            return i
        i += step
    return None

def _step_should_shift(s, p):
    if len(s) - p < 3:
        return False
    c, step = get_valid_char(s, p)
    if step != 2:
        return False
    c, step = get_valid_char(s, p + 1)
    if step != 2:
        return False
    return True

def _valid_shift_jis_text(s, p):
    thp = trim_invalid_head(s, p)
    if thp is None:
        return None, None
    i = thp
    rs = ''
    sjc = 0
    if _step_should_shift(s, thp):
        nxt = thp + 1
    else:
        nxt = None
    gnxt = lambda v: v if nxt is None else nxt
    while i < len(s):
        c, step = get_valid_char(s, i)
        if c is None:
            return None, gnxt(i)
        try:
            rc = c.decode('shift-jis')
        except:
            return None, gnxt(i)
        i += step
        rs += rc
        if step == 2:
            sjc += 1
    if sjc < 2:
        return None, nxt
    if invalid_spec_text(s, thp):
        return None, nxt
    if thp > 0:
        if invalid_spec_text_trimed(s, thp):
            return None, nxt
    if ' 'in rs:
        if invalid_spec_text_spaced(rs):
            return None, nxt
    if rs in invalid_spec_list:
        return None, nxt
    return rs, thp

def valid_shift_jis_text(s):
    rs = None
    thp = 0
    while rs is None and not thp is None:
        rs, thp = _valid_shift_jis_text(s, thp)
    return rs, thp

EOS = 0 #b'\00'
class c_text_finder:

    def __init__(self, raw, offset = 0,
                 checker = valid_shift_jis_text):
        self.raw = raw
        self.pos = offset
        self.checker = checker
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
    def count_bytes(s):
        n = 0
        for c in s:
            if len(c.encode('utf-8')) > 1:
                n += 2
            else:
                n += 1
        return n

    @staticmethod
    def valid_trans(txt_itm, chk_at = True):
        if not txt_itm['trans']:
            return None, None
        src = txt_itm['text']
        trans = txt_itm['trans']
        if chk_at and (src[-1] == '@') != (
            trans[-1] == '@'):
            raise ValueError('missed @ symbol')
        slen = c_text_finder.count_bytes(src)
        dlen = c_text_finder.count_bytes(trans)
        if txt_itm['info'][0] % 2 and src[0] == ' ':
            if trans[0] != ' ':
                raise ValueError('trans need to be pad by space')
            trans_nopad = trans[1:]
        else:
            trans_nopad = trans
        if not valid_ctr_sym_in_string(trans_nopad):
            raise ValueError('invalid symbol in trans')
        if slen + txt_itm['info'][2] - 1 < dlen:
            raise ValueError('trans too long')
        elif dlen < slen:
            trans += '\00' * (slen - dlen)
        return trans, txt_itm['info'][0]

if __name__ == '__main__':
    pass


