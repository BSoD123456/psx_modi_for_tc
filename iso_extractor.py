#! python3
# coding: utf-8

import os, os.path
import shutil

EXT_TOOL = 'tools/isodump.exe'
MOD_TOOL = 'tools/psx-mode2-en.exe'

EXT_CMD = '{:s} "{:s}" -x "{:s}"'
MOD_CMD = '{:s} "{:s}" \\{:s} "{:s}"'

EXT_TOOL = os.path.abspath(EXT_TOOL)
MOD_TOOL = os.path.abspath(MOD_TOOL)

class c_iso_extractor:

    def __init__(self, src_fname, ext_path = r'table\ext', mod_path = None):
        self.src_fname = os.path.abspath(src_fname)
        if not os.path.exists(self.src_fname):
            raise ValueError('src file not exist')
        self.ext_path = os.path.abspath(ext_path)
        if not os.path.exists(self.ext_path):
            os.makedirs(self.ext_path)
        if not mod_path:
            mod_path = ext_path
        self.mod_path = os.path.abspath(mod_path)
        if not os.path.exists(self.mod_path):
            os.makedirs(self.mod_path)

    def get_path(self, typ, fname = ''):
        if typ == 'ext':
            path = self.ext_path
        elif typ == 'mod':
            path = self.mod_path
        return os.path.join(path, fname)

    def extract(self, tarlist = []):
        for tar in tarlist:
            p = self.get_path('ext', tar)
            if not os.path.exists(p):
                break
        else:
            if len(tarlist) > 0:
                return True
        cmd = EXT_CMD.format(EXT_TOOL, self.src_fname, self.ext_path)
        if os.system(cmd) == 0:
            return True
        else:
            return False

    def modify(self, out_fn):
        shutil.copy(self.src_fname, out_fn)
        for fn in os.listdir(self.mod_path):
            cmd = MOD_CMD.format(MOD_TOOL,
                                 out_fn, fn,
                                 os.path.join(self.mod_path, fn))
            if os.system(cmd) != 0:
                return False
        return True
    
if __name__ == '__main__':

    iso_file = r'G:\emu\ps\roms\Tail Concerto (Japan).bin'
    
    extr = c_iso_extractor(iso_file)
