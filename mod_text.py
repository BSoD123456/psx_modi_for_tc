#! python3
# coding: utf-8

import os, os.path
import json

from collections import OrderedDict

from find_sj_text import c_text_finder
from mod_charset import std_filler

class c_text_tab:

    VERSION = 1.0

    def __init__(self, srcs):
        self.texts = []
        self.filler = std_filler()
        self.srclist = OrderedDict(srcs)
        self.scan_done = False
        self.import_done = False
        self.modified = False
        self.texts_fname = None
        
    def scan_raw_text(self, raw, tag):
        print('scan', tag)
        tfinder = c_text_finder(raw)
        tfinder.scan()
        if tfinder.text_list and len(tfinder.text_list) > 0:
            self.texts.append((tag, tfinder.text_list))

    def scan_text(self, scanner, tag):
        for raw, stag in scanner.iter_ukraw():
            self.scan_raw_text(raw, tag + ':' + stag)

    def scan(self):
        if self.scan_done:
            return
        for tag, src in self.srclist.items():
            if isinstance(src, bytes):
                self.scan_raw_text(src, tag)
            else:
                self.scan_text(src, tag)
        self.scan_done = True

    def import_texts(self):
        if not self.scan_done:
            return
        for tag, txt_group in self.texts:
            tag = tag.split(':')
            offset = 0
            if len(tag) > 1:
                offset = int(tag[1].split('_')[0], 16)
            tag = tag[0]
            raw = self.srclist[tag]
            if not isinstance(raw, bytes):
                raw = raw.raw
            for txt_info in txt_group:
                try:
                    txt_trans, txt_offset = c_text_finder.valid_trans(txt_info)
                    if not txt_trans:
                        continue
                    encode_trans = b''
                    for c in txt_trans:
                        ec = c.encode('utf-8')
                        if len(ec) == 1:
                            encode_trans += ec
                            continue
                        encode_trans += self.filler.emit(c)
                except Exception as e:
                    print('error ocured for trans: ' + str(txt_info))
                    raise e
                sofs = txt_offset + offset
                eofs = sofs + len(encode_trans)
                self.modified = True
                raw = raw[:sofs] + encode_trans + raw[eofs:]
            self.srclist[tag] = raw
        self.import_done = True

    def save_texts(self, texts_fn = None):
        if texts_fn:
            self.texts_fname = texts_fn
        else:
            texts_fn = self.texts_fname
        with open(texts_fn, 'w', encoding='utf-8') as fd:
            json.dump({
                'meta': {'version': self.VERSION},
                'texts': self.texts,
            }, fd, ensure_ascii = False)
        
    def load_texts(self, texts_fn):
        self.texts_fname = texts_fn
        try:
            with open(texts_fn, 'r', encoding='utf-8') as fd:
                self.texts = json.load(fd)
        except:
            self.scan()
            self.save_texts()
        else:
            if not (isinstance(self.texts, dict) and
                    'meta' in self.texts and
                    'version' in self.texts['meta'] and
                    self.texts['meta']['version'] >= self.VERSION):
                old_texts = self.texts
                self.texts = []
                self.scan()
                self.update_old_texts(old_texts)
                self.save_texts()
            else:
                self.texts = self.texts['texts']
            self.scan_done = True

    def update_old_texts(self, old_texts):
        print('update old texts to version', str(self.VERSION))
        if (isinstance(self.texts, dict) and            
            'texts' in self.texts):
            old_texts = old_texts['texts']
        now_texts = self.texts
        merge_texts = []
        n_s_idx = 0
        o_s_idx = 0
        while n_s_idx < len(now_texts) or o_s_idx < len(old_texts):
            try:
                n_sec = now_texts[n_s_idx]
            except:
                n_sec = (None, None)
            try:
                o_sec = old_texts[o_s_idx]
            except:
                o_sec = (None, None)
            if n_sec[0] == o_sec[0]:
                tag = n_sec[0]
                n_itms = n_sec[1]
                o_itms = o_sec[1]
                n_s_idx += 1
                o_s_idx += 1
                n_t_idx = 0
                o_t_idx = 0
                m_itms = []
                while n_t_idx < len(n_itms) or o_t_idx < len(o_itms):
                    empty_ti = {
                        'text': None,
                        'info': [float('inf'), 0, 0],
                    }
                    try:
                        n_ti = n_itms[n_t_idx]
                    except:
                        n_ti = empty_ti
                    try:
                        o_ti = o_itms[o_t_idx]
                    except:
                        o_ti = empty_ti
                    n_ofs = n_ti['info'][0]
                    o_ofs = o_ti['info'][0]
                    ofs_dist = abs(n_ofs - o_ofs)
                    if ofs_dist < 3:
                        trans = o_ti['trans']
                        if trans:
                            if ofs_dist > 0:
                                trans = '*need update*' + trans
                            n_ti['trans'] = trans
                        m_itms.append(n_ti)
                        n_t_idx += 1
                        o_t_idx += 1
                    elif n_ofs < o_ofs:
                        m_itms.append(n_ti)
                        n_t_idx += 1
                    elif n_ofs > o_ofs:
                        o_ti['trans'] = '*no longer exist*' + o_ti['trans']
                        o_itms.append(o_ti)
                        o_t_idx += 1
                merge_texts.append((tag, m_itms))
            else:
                has_n = (n_sec[0] in (s[0] for s in old_texts[o_s_idx:]))
                has_o = (o_sec[0] in (s[0] for s in now_texts[n_s_idx:]))
                if has_n and has_o:
                    raise ValueError('invalid texts sect order')
                if not has_n:
                    merge_texts.append(n_sec)
                    n_s_idx += 1
                if not has_o:
                    merge_texts.append(o_sec)
                    o_s_idx += 1
        self.texts = merge_texts

    @staticmethod
    def touch_timestamp(stmp_fn):
        if not stmp_fn:
            return
        try:
            with open(stmp_fn, 'w') as fd:
                pass
        except:
            pass

    @staticmethod
    def check_timestamp(dst_fn, stmp_fn, touch = True):
        if not (stmp_fn and dst_fn and
                os.path.exists(dst_fn)):
            return False
        ts_t = os.path.getmtime(dst_fn)
        if os.path.exists(stmp_fn):
            ts_s = os.path.getmtime(stmp_fn)
        else:
            ts_s = 0
        if ts_t > ts_s:
            if touch:
                c_text_tab.touch_timestamp(stmp_fn)
            return True
        return False

    def write_files(self, fn_prefix, stamp = None, force = False):
        if not self.import_done:
            self.import_texts()
        if stamp:
            if force:
                self.touch_timestamp(stamp)
            elif not self.check_timestamp(self.texts_fname, stamp):
                return False
        if not force and not self.modified:
            return False
        for tag, raw in self.srclist.items():
            if not isinstance(raw, bytes):
                raw = raw.raw
            with open(fn_prefix + tag, 'wb') as fd:
                fd.write(raw)
        return True

if __name__ == '__main__':

    pass
