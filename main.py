#! python3
# coding: utf-8

import os, os.path
import json

import configparser

from find_tim import c_tim_scanner
from find_sj_text import c_text_finder
from mod_text import c_text_tab
from iso_extractor import c_iso_extractor

if __name__ == '__main__':

    cfg_file = 'config.txt'

    def load_config():
        cfg = configparser.ConfigParser()
        if os.path.exists(cfg_file):
            cfg.read(cfg_file)
        else:
            cfg.update({
                'DEFAULT': {
                    'iso_file': r'roms\Tail Concerto (Japan).bin',
                    'ext_path': r'table\ext',
                    'mod_path': r'table\mod',
                    'sav_path': r'table\sav',
                    'out_path': r'table\out',
                    'main_file': 'SLPS_012.99',
                    'data_file': 'DATA.BIN',
                    'modbios_file': 'SCPH1001MOD.BIN',
                    'modios_file': 'Tail Concerto (zh).bin',}})
            with open(cfg_file, 'w') as fd:
                cfg.write(fd)
        return cfg
    
    def main(force = False):

        cfg = load_config()

        savp = lambda p: os.path.join(cfg['DEFAULT']['sav_path'], p)
        if not os.path.exists(cfg['DEFAULT']['sav_path']):
            os.makedirs(cfg['DEFAULT']['sav_path'])
        outp = lambda p: os.path.join(cfg['DEFAULT']['out_path'], p)
        if not os.path.exists(cfg['DEFAULT']['out_path']):
            os.makedirs(cfg['DEFAULT']['out_path'])

        extractor = c_iso_extractor(
            cfg['DEFAULT']['iso_file'],
            cfg['DEFAULT']['ext_path'],
            cfg['DEFAULT']['mod_path'])
        extractor.extract([cfg['DEFAULT']['main_file'], cfg['DEFAULT']['data_file']])
        ext_main = extractor.get_path('ext', cfg['DEFAULT']['main_file'])
        ext_data = extractor.get_path('ext', cfg['DEFAULT']['data_file'])
        if not (os.path.exists(ext_main) and
                os.path.exists(ext_data)):
            raise RuntimeError('invalid src file')

        with open(ext_main, 'rb') as fd:
            main_raw = fd.read()

        scan_sav = 'scan.json'
        with open(ext_data, 'rb') as fd:
            data_scanner = c_tim_scanner(fd.read())
        data_scanner.load_scan(savp(scan_sav))

        text_sav = 'texts.json'
        text_tab = c_text_tab({
            cfg['DEFAULT']['main_file']: main_raw,
            cfg['DEFAULT']['data_file']: data_scanner,
        })
        text_tab.load_texts(savp(text_sav))
        
        text_timestamp = 'timestamp'
        if text_tab.write_files(extractor.get_path('mod'),
                                savp(text_timestamp)):
            text_tab.filler.save_set(outp(cfg['DEFAULT']['modbios_file']))
            extractor.modify(outp(cfg['DEFAULT']['modios_file']))
            if not os.path.exists(outp(cfg['DEFAULT']['modios_file'])):
                raise RuntimeError('iso modify failed')
        
        return text_tab
    
    try:
        text_tab = main()
    except KeyboardInterrupt:
        print('break')
    except Exception as e:
        print('error')
        print(e)
        input('')
        raise e

    
