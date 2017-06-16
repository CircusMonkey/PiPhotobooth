from os import listdir, makedirs, walk
from os.path import join, basename, dirname, exists, isfile
import re
import gc

import main

from kivy.uix.screenmanager import Screen
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.image import AsyncImage
from kivy.uix.gridlayout import GridLayout
from kivy.uix.popup import Popup
from kivy.uix.scatter import Scatter
from kivy.graphics.transformation import Matrix

from PIL import Image

import qrcode

import globals_      # Import global variables


'''
Hybrid class allowing images to take some properties belonging to
buttons. Used for the photoviewer.
'''
class ImgButton(ButtonBehavior, AsyncImage):
    def on_press(self):
        # Setup the scatter layout to show in the popup
        scatter = Scatter(do_rotation = False, size_int = (300, 300), scale_min=1.0, scale_max=10.0)

        image_source = join(globals_.photo_path, 'thumbs', basename(self.source))

        image = AsyncImage(source = image_source)
        scatter.add_widget(image)
        # Resize the scatter object
        multiplier = 6
        mat = Matrix().scale(multiplier, multiplier, multiplier)
        scatter.apply_transform(mat)

        popup = Popup(title = basename(self.source),
                      content = scatter,
                      size_hint = (0.8, 1),
                      pos_hint = {'x':0.0, 'y':0.0})
        popup.open()

'''
Screen to display single photo
'''
class SinglePhotoScreen(Screen):
    pass

'''
Screen to display all the photos
'''
class PhotoviewerScreen(Screen):
    photo_page = 0
    photo_list = []
    thumb_size = (800, 480)

    def on_enter(self):
        # Refresh the qr code
        self.ids.qr_code.reload()

        # Generate thumbs of the photos
        Thumbnailer()

        # Make sure the height is such that there is something to scroll.
        self.ids.picGrid.bind(minimum_height=self.ids.picGrid.setter('height'))

        # Update the photo list
        self.photo_list = listdir(join(globals_.photo_path, 'thumbs'))
        self.photo_list.sort(reverse=True)
        j = 0
        for photo in self.photo_list:
            j = j+1
            print("%d - %s" % (j,photo))

        # Get the 4 latest photos
        self.photo_page = 0
        print "Number of photos in list: " + str(len(self.photo_list))
        print "Number of pages: " + str(len(self.photo_list) / 4 + 1)
        if self.photo_page >= len(self.photo_list) / 4:
            self.ids.next_button.disabled = True
        else:
            self.ids.next_button.disabled = False
        self.init_photo_thumbs()
        self.refresh_photo_thumbs()


    def on_leave(self):
        self.ids.picGrid.clear_widgets()
        gc.collect()


    def init_photo_thumbs(self):
        for i in range(4):
            img = ImgButton()
            self.ids.picGrid.add_widget(img)


    def refresh_photo_thumbs(self):
        i = self.photo_page*4
        for child in reversed(self.ids.picGrid.children[:]):
            if (self.photo_page*4 + i % 4 < len(self.photo_list)):
                # Check if the file is a photo
                if self.photo_list[i].endswith('.jpg'):
                    child.source = join(globals_.photo_path, 'thumbs', self.photo_list[i])
                    print("Displaying %d : %s" % (i,str(self.photo_list[i])))
                    #child.reload()
                    i = i + 1
                else:
                    print("Failed: " + str(self.photo_list[i]))
            else:
                child.source = ""
        gc.collect()


    def next_page(self):
        self.photo_page = self.photo_page + 1

        self.ids.prev_button.disabled = False
        if self.photo_page >= len(self.photo_list) / 4:
            self.ids.next_button.disabled = True

        self.refresh_photo_thumbs()


    def prev_page(self):
        self.photo_page = self.photo_page - 1

        self.ids.next_button.disabled = False
        if self.photo_page <= 0:
            self.ids.prev_button.disabled = True

        self.refresh_photo_thumbs()



'''
Reloads the qr code jpg to the new setting
'''
def create_qr_code(text):
    print "Creating qr code for {0}".format(text)
    img = qrcode.make(text)

    # Save the image. The Pi doesn't like the image the qrcode spits out
    # so the thumbnail function is used to convert it somehow, so it displays on the Pi.
    size = (300, 300)
    img.thumbnail(size)
    img.save(join(dirname(__file__), 'img', 'qr.jpg'), format='jpeg')


'''
Scans the photo folder to see if there is a thumbnail for each image.
Raspberry Pi only has enough juice to display small thumbnails and not
full resolution photos.
'''
def Thumbnailer():
    size = (400, 240)
    # Check for thumbnail directory
    if not exists(join(globals_.photo_path, 'thumbs')):
        makedirs(join(globals_.photo_path, 'thumbs'))
    # Go through the photos one at a time
    files = listdir(globals_.photo_path)
    for file_ in files:
        # Check if the file is a photo
        if file_.endswith('.jpg'):
            # Check for missing corresponding photo thumbnail
            if exists(join(globals_.photo_path, 'thumbs', file_)) == False:
                create_thumbnail(globals_.photo_path, file_, size)


'''
Creates a thumbnail image in a thumbs directory where the original photo is located.
Resulting file has the same filename.
'''
def create_thumbnail(path, file_, size):
    # Check for thumbnail directory
    if not exists(join(globals_.photo_path, '.thumbs')):
        makedirs(join(globals_.photo_path, '.thumbs'))
    try:
        im = Image.open(join(path, file_))
        im.thumbnail(size)
        im.save(join(path, 'thumbs', file_), "JPEG")
    except IOError:
        print "Cannot create thumbnail for " + join(path, 'thumbs', file_)
