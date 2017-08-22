from os.path import join, dirname
from os import walk
from PIL import Image


def Main():
    for root, dirs, files in walk(dirname(__file__)):
        for file_ in files:
            # Check if the file is a photo
            if file_.endswith('.jpg'):
                # Open the photo and flip it horizontally
                photo = Image.open(join(dirname(__file__), file_))
                photo = photo.transpose(Image.FLIP_LEFT_RIGHT)
                print('Flipping %s' % file_)
                # Save the image
                photo.save(join(dirname(__file__), file_))


if __name__ == "__main__":
    # Start the main app
    Main()
