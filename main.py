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
        drity = False
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
            drity = True
        if not 'TIM' in cfg:
            cfg.update({
                'TIM': {
                    'enable': 'off',
                    'tim_path': r'tim',}})
            drity = True
        if not 'TIMCONV' in cfg:
            cfg.update({
                'TIMCONV': {
                    'enable': 'off',
                    'png_path': r'png',}})
            drity = True
        if drity:
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

        tim_imported = False
        use_mod_data = False
        if cfg['TIM']['enable'] != 'off':
            tim_ext_path = os.path.join(
                cfg['DEFAULT']['ext_path'], cfg['TIM']['tim_path'])
            if not os.path.exists(tim_ext_path):
                os.makedirs(tim_ext_path)
            textp = lambda p: os.path.join(tim_ext_path, p)
            tim_sav_path = os.path.join(
                cfg['DEFAULT']['sav_path'], cfg['TIM']['tim_path'])
            if not os.path.exists(tim_sav_path):
                os.makedirs(tim_sav_path)
            tsavp = lambda p: os.path.join(tim_sav_path, p)
            
            data_scanner.save_files(tim_ext_path, target = ['tim'])

            if cfg['TIMCONV']['enable'] != 'off':
                
                from convert_tim import c_tim_converter
                
                png_ext_path = os.path.join(
                    cfg['DEFAULT']['ext_path'], cfg['TIMCONV']['png_path'])
                if not os.path.exists(png_ext_path):
                    os.makedirs(png_ext_path)
                pextp = lambda p: os.path.join(png_ext_path, p)
                png_sav_path = os.path.join(
                    cfg['DEFAULT']['sav_path'], cfg['TIMCONV']['png_path'])
                if not os.path.exists(png_sav_path):
                    os.makedirs(png_sav_path)
                psavp = lambda p: os.path.join(png_sav_path, p)

                timconv_tab = {}
                def get_timconv(tag):
                    if tag in timconv_tab:
                        tc = timconv_tab[tag]
                    else:
                        fn = textp(tag + '.tim')
                        if not os.path.exists(fn):
                            return None
                        try:
                            with open(fn, 'rb') as fd:
                                tc = c_tim_converter(fd.read())
                        except ValueError as e:
                            if e.args[0] == 'empty body':
                                return None
                            raise
                        timconv_tab[tag] = tc
                    return tc
                
                for fn in os.listdir(tim_ext_path):
                    tag = fn.split('.')[0]
                    if fn.split('.')[-1] != 'tim':
                        continue
                    pfn = tag + '.png'
                    if not os.path.exists(pextp(pfn)):
                        timconv = get_timconv(tag)
                        if not timconv:
                            continue
                        print('convert to png: ' + tag)
                        timconv.save_png(pextp(pfn))

                for fn in os.listdir(png_sav_path):
                    tag = fn.split('.')[0]
                    if fn.split('.')[-1] != 'png':
                        continue
                    tfn = tag + '.tim'
                    need_conv = True
                    if os.path.exists(tsavp(tfn)):
                        ts_t = os.path.getmtime(tsavp(tfn))
                        ts_p = os.path.getmtime(psavp(fn))
                        if ts_t >= ts_p:
                            need_conv = False
                    if need_conv:
                        timconv = get_timconv(tag)
                        if not timconv:
                            continue
                        print('convert to tim: ' + tag)
                        timconv.load_png(psavp(fn))
                        with open(tsavp(tfn), 'wb') as fd:
                            fd.write(timconv.raw)

            tim_timestamp = 'tim_timestamp'
            for fn in os.listdir(tim_sav_path):
                if not os.path.exists(textp(fn)):
                    continue
                try:
                    tim_ofs = int(fn.split('_')[0], 16)
                except:
                    continue
                if not c_text_tab.check_timestamp(
                    tsavp(fn), savp(tim_timestamp), False):
                    continue
                tim_imported = True
                with open(tsavp(fn), 'rb') as fd:
                    if not data_scanner.import_file(fn, fd.read()):
                        raise RuntimeError('invalid tim file: ' + fn)
            if tim_imported:
                print('tim imported')
                c_text_tab.touch_timestamp(savp(tim_timestamp))
            else:
                mod_data_fn = extractor.get_path(
                    'mod', cfg['DEFAULT']['data_file'])
                if os.path.exists(mod_data_fn):
                    with open(mod_data_fn, 'rb') as fd:
                        data_scanner.raw = fd.read()
                    use_mod_data = True
        
        text_timestamp = 'timestamp'
        if text_tab.write_files(extractor.get_path('mod'),
                                savp(text_timestamp), tim_imported):
            if use_mod_data:
                print('use old ' + cfg['DEFAULT']['data_file'])
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

    
