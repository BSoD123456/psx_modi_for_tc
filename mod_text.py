#! python3
# coding: utf-8

import os, os.path
import json

from collections import OrderedDict

from find_sj_text import c_text_finder
from mod_charset import std_filler

class c_text_tab:

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
                        if c in ['@', '\00']:
                            encode_trans += c.encode('utf-8')
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
            json.dump(self.texts, fd, ensure_ascii = False)
        
    def load_texts(self, texts_fn):
        self.texts_fname = texts_fn
        try:
            with open(texts_fn, 'r', encoding='utf-8') as fd:
                self.texts = json.load(fd)
            self.scan_done = True
        except:
            self.scan()
            self.save_texts()

    @staticmethod
    def touch_timestamp(stmp_fn):
        if not stmp_fn:
            return
        try:
            with open(stmp_fn, 'w') as fd:
                pass
        except:
            pass
        
    def check_timestamp(self, stmp_fn):
        if not (stmp_fn and self.texts_fname and
                os.path.exists(self.texts_fname)):
            return False
        ts_t = os.path.getmtime(self.texts_fname)
        if os.path.exists(stmp_fn):
            ts_s = os.path.getmtime(stmp_fn)
        else:
            ts_s = 0
        if ts_t > ts_s:
            self.touch_timestamp(stmp_fn)
            return True
        return False

    def write_files(self, fn_prefix, stamp = None):
        if not self.import_done:
            self.import_texts()
        if stamp and not self.check_timestamp(stamp):
            return False
        if not self.modified:
            return False
        for tag, raw in self.srclist.items():
            with open(fn_prefix + tag, 'wb') as fd:
                fd.write(raw)
        return True

if __name__ == '__main__':

    pass
