from __future__ import print_function
import sys
from os.path import join, dirname
from os import walk
from PIL import Image


def Main():
    imgcount = 0
    count = 0
    
    for root, dirs, files in walk(dirname(__file__)):
        for infile in files:
            
            try:
                with Image.open(infile) as im:
                    print(infile, im.format, "%dx%d" % im.size, im.mode)
                    imgcount = imgcount + 1
            except IOError:
                pass
            
            count = count + 1

    print('Done. %d/%d are images' % (imgcount, count))



if __name__ == "__main__":
    # Start the main app
    Main()
