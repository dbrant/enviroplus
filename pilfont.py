#!/usr/bin/env python
# Author: Peter Samuel Anttila
# License: The Unlicense <http://unlicense.org, October 16 2018>
from PIL import BdfFontFile
from PIL import PcfFontFile
import os
import glob

font_file_paths = []
current_dir_path = os.path.dirname(os.path.abspath(__file__))
font_file_paths.extend(glob.glob(current_dir_path+"/*.bdf"))
font_file_paths.extend(glob.glob(current_dir_path+"/*.pcf"))

for font_file_path in font_file_paths:    
    try:
        with open(font_file_path,'rb') as fp:
            # despite what the syntax suggests, .save(font_file_path) won't 
            # overwrite your .bdf files, it just creates new .pil and .pdm
            # files in the same folder
            if font_file_path.lower().endswith('.bdf'):
                p = BdfFontFile.BdfFontFile(fp)
                p.save(font_file_path)
            elif font_file_path.lower().endswith('.pcf'):
                p = PcfFontFile.PcfFontFile(fp)
                p.save(font_file_path)
            else:
                # sanity catch-all
                print("Unrecognized extension.")
    except (SyntaxError,IOError) as err:
        print("File at '"+str(font_file_path)+"' could not be processed.")
        print("Error: " +str(err))
