from os.path import join, dirname
from os import walk
from PIL import Image, ImageEnhance


def Main():
    count = 0
    for root, dirs, files in walk(dirname(__file__)):
        for file_ in files:
            # Check if the file is a photo
            if file_.endswith('.jpg'):
                
                # Open the photo
                im = Image.open(join(dirname(__file__), file_))

                # Edit the photo
                print('Adjusting %s' % file_)

                enh = do_gamma(im, 2.0)
                
                #enh.show('Enhanced')


                # Save the image
                enh.save(join(dirname(__file__), file_))
                count = count + 1

    print('Done. Changed %d images' % count)


def do_gamma(im, gamma):
    """Fast gamma correction with PIL's image.point() method"""
    invert_gamma = 1.0/gamma
    lut = [pow(x/255., invert_gamma) * 255 for x in range(256)]
    lut = lut*3 # need one set of data for each band for RGB
    im = im.point(lut)
    return im


if __name__ == "__main__":
    # Start the main app
    Main()
