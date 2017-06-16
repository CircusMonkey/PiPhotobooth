'''
#-------------------------------------------#
#-- Import Modules -------------------------#
#-------------------------------------------#
'''

import globals_      # Import global variables
import main
from photoviewer import create_thumbnail
import dropbox
import dropbox_stuff
from image_postprocessing import *

from subprocess import call
import threading
from time import sleep
from datetime import datetime
from os import walk
from os.path import join, dirname
import json
from random import randint
from functools import partial
import io
from PIL import Image


try:
    import picamera
    import RPi.GPIO as GPIO
except:
    print "Error: Couldn't import picamera or RPi.GPIO"

# Kivy modules
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.slider import Slider
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.switch import Switch


'''
#-------------------------------------------#
#-- Camera Stuff ---------------------------#
#-------------------------------------------#
'''

global camera

class PhotoboothScreen(Screen):
    def on_enter(self):
        '''
        Starts the camera preview window in a new thread.
        '''
        # Check the camera isnt already running
        try:
            threading.Thread(target = enable_camera).start()
        except:
            print 'Error: Could not initialise camera'


class PhotoboothSequenceScreen(Screen):
    def on_leave(self):
        if (main.App.get_running_app().config.getint('Camera', 'flash_always_on') == '0'):
            # Turn the flash off
            flash_brightness(0)

        # Reset the countdown image
        change_countdown('clear')

    def take_photo_init(self):
        threading.Thread(target = take_photo).start()


class SettingsLiteScreen(Screen):
    def __init__(self, **kwargs):
        super(SettingsLiteScreen, self).__init__(**kwargs)

        # Set up the settings in a grid
        popup = GridLayout(cols=1, size_hint_y=None)
        # Make sure the height is such that there is something to scroll.
        popup.bind(minimum_height=popup.setter('height'))

        # Set up setting buttons
        with open(join(dirname(__file__), 'camera.json')) as json_file:
            json_data = json.load(json_file)
            for setting in json_data:
                if setting['settings_lite'] == '1':

                    # Check if the setting is boolean
                    if setting['type'] == 'bool':

                        # Check if the current setting is on or off
                        if main.App.get_running_app().config.getint('Camera', setting['key']) == 1:
                            cur_state = True
                        else:
                            cur_state = False

                        # Create the widgets
                        label = Label(text=setting['title'],
                                     size_hint_y=None,
                                     height=48)
                        switch = Switch(active=cur_state,
                                    size_hint_y=None,
                                    height=48)
                        switch.bind(active=partial(self.settings_lite_switch_toggle, setting['key']))
                        # Add to main settings_lite widget
                        popup.add_widget(label)
                        popup.add_widget(switch)

                    # Else just make the setting a button
                    else:
                        btn = Button(text=setting['title'],
                                     size_hint_y=None,
                                     height=96)
                        btn.bind(on_release=self.settings_lite_button_push)
                        popup.add_widget(btn)

        # Setup the scrollable section and add to floatlayout.
        scrolly = ScrollView(size_hint=(0.2, 0.83),
                             pos_hint={'x':0.8, 'y':0.17})
        scrolly.add_widget(popup)
        floaty = FloatLayout()
        floaty.add_widget(scrolly)

        # Add the close button to the bottom
        close_button = Button(text='Close',
                              size_hint=(0.2, 0.16),
                              pos_hint={'x':0.8, 'y':0})
        close_button.bind(on_release=self.close_settings_lite)
        floaty.add_widget(close_button)
        self.add_widget(floaty)


    def settings_lite_switch_toggle(self, key, instance, value):
        '''
        Change the setting of the switch that is toggled.
        '''
        print "Setting {0} to {1}".format(key, value)
        # Convert value variable to required boolean format
        if ("camera." in key):
			# Change camera setting
			exec compile('{0} = value'.format(key), '<string>', 'exec')
        elif value == True:
			value = 1
        else:
            value = 0
		# Write changes to .ini file
        main_app = main.App.get_running_app()
        main_app.config.set('Camera', key, value)
        main_app.config.write()

        if (key == 'flash_always_on'):
			flash_brightness() # Turns off or on accordingly


    def settings_lite_button_push(self, instance):
        '''
        Change the setting of the button that is pushed.
        '''
        global cur_setting

        with open(join(dirname(__file__), 'camera.json')) as json_file:
            json_data = json.load(json_file)
            for setting in json_data:
                if setting['title'] == instance.text:
                    # Save the setting so it can be configured in the next screen
                    cur_setting = setting
                    if setting['type'] == 'options':
                        self.show_options()
                    elif setting['type'] == 'numeric':
                        self.show_numeric_slider()
                    break

    def show_numeric_slider(self):
        globals_.scr_manager.transition.direction = 'left'
        globals_.scr_manager.current = 'settings_lite_slider'

    def show_options(self):
        globals_.scr_manager.transition.direction = 'left'
        globals_.scr_manager.current = 'settings_lite_options'

    def close_settings_lite(self, instance):
        globals_.scr_manager.transition.direction = 'down'
        globals_.scr_manager.current = 'photobooth'


class SettingsLiteSliderScreen(Screen):
    def __init__(self, **kwargs):
        super(SettingsLiteSliderScreen, self).__init__(**kwargs)

        label = Label()

    def on_pre_enter(self):
        # Set up the slider
        slider = Slider(min=int(cur_setting['min']),
                        max=int(cur_setting['max']),
                        value=main.App.get_running_app().config.getint('Camera', cur_setting['key']),
                        orientation='vertical',
                        size_hint=(0.2, 0.75),
                        pos_hint={'x':0.8, 'y':0.17},
                        step=1)

        # Add a label up the top showing the slider value
        self.label = Label(text='{0}: {1}'.format(cur_setting['title'], int(slider.value)),
                      size_hint=(0.2, 0.1),
                      pos_hint={'x':0.8, 'y':0.9})

        # Add the close button to the bottom
        back_button = Button(text='Back',
                            size_hint=(0.2, 0.16),
                            pos_hint={'x':0.8, 'y':0})

        # Bind the events
        slider.bind(value=self.change_setting)
        back_button.bind(on_release=self.back_button_press)

        # Add to floatlayout.
        floaty = FloatLayout()
        floaty.add_widget(slider)
        floaty.add_widget(self.label)
        floaty.add_widget(back_button)
        self.add_widget(floaty)

    def on_leave(self):
        self.clear_widgets()

    def change_setting(self, instance, value):
        print "Setting {0} to {1}".format(cur_setting['title'], value)
        # Special case
        if cur_setting['key'] == 'pre_flash':
        	flash_brightness(value)
        else:
			# Change camera setting
			exec compile('{0} = int(value)'.format(cur_setting['key']), '<string>', 'exec')

        # Update label value
        self.label.text='{0}: {1}'.format(cur_setting['title'], int(value))

        # Write changes to .ini file
        main_app = main.App.get_running_app()
        main_app.config.set('Camera', cur_setting['key'], '{0}'.format(int(value)))
        main_app.config.write()

    def back_button_press(self, instance):
        globals_.scr_manager.transition.direction = 'right'
        globals_.scr_manager.current = 'settings_lite'


class SettingsLiteOptionsScreen(Screen):
    def __init__(self, **kwargs):
        super(SettingsLiteOptionsScreen, self).__init__(**kwargs)

    def on_pre_enter(self):
        # Set up the settings in a grid
        popup = GridLayout(cols=1, size_hint_y=None)
        # Make sure the height is such that there is something to scroll.
        popup.bind(minimum_height=popup.setter('height'))

        # Set up the buttons
        for each in cur_setting['options']:
            btn = Button(text=each,
                         size_hint_y=None,
                         height=96)
            btn.bind(on_release=self.change_setting)
            popup.add_widget(btn)

        # Setup the scrollable section and add to floatlayout.
        scrolly = ScrollView(size_hint=(0.2, 0.83),
                             pos_hint={'x':0.8, 'y':0.17})
        scrolly.add_widget(popup)
        floaty = FloatLayout()
        floaty.add_widget(scrolly)

        # Add the close button to the bottom
        back_button = Button(text='Back',
                              size_hint=(0.2, 0.16),
                              pos_hint={'x':0.8, 'y':0})
        back_button.bind(on_release=self.back_button_press)
        floaty.add_widget(back_button)

        self.add_widget(floaty)

    def on_leave(self):
        # Clear the button widgets from the scrollview
        self.clear_widgets()

    def change_setting(self, instance):

        print "Setting {0} to {1}".format(cur_setting['title'], instance.text)

        # Change the camera setting to the value. Convert to int if required.
        try:
            exec compile('{0} = instance.text'.format(cur_setting['key']), '<string>', 'exec')
        except TypeError:
            exec compile('{0} = int(instance.text)'.format(cur_setting['key']), '<string>', 'exec')

        # Write changes to .ini file


    def back_button_press(self, instance):
        globals_.scr_manager.transition.direction = 'right'
        globals_.scr_manager.current = 'settings_lite'


'''
Functions to control the LED flash via PWM
'''
def init_pwm(pin):
    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(pin, GPIO.OUT) # Pin 21 as output
        globals_.flash = GPIO.PWM(pin, 100) # Pin 21 as PWM @ 100Hz
        # Set initial duty cycle to 0
        globals_.flash.start(0)
        print "Successfully setup PWM"
    except:
        print "Error: Could not initialise PWM"

def stop_pwm():
    try:
        globals_.flash.stop()
        GPIO.cleanup()
        print('PWM stopped')
    except:
        print('Error: Could not stop PWM')

def flash_brightness(duty_cycle=0):
    global flash
    settings = main.App.get_running_app().config

    # Flash is disabled
    if settings.getint('Camera', 'flash_enabled') == 0:
        duty_cycle = 0
    # Flash is always on
    elif duty_cycle == 0 and settings.getint('Camera', 'flash_always_on') == 1:
        duty_cycle = settings.getint('Camera', 'pre_flash')

    # Change the duty cycle
    try:
        globals_.flash.ChangeDutyCycle(duty_cycle)
        print "Flash brightness changed to " + str(duty_cycle)
    except:
    	print "Error: Could not change flash brightness to " + str(duty_cycle)



'''
Initiates the photo countdown and takes a series of photos
'''
def change_photo_count(count, total):
    # Get the widget
    screen = globals_.scr_manager.get_screen('photobooth_sequence')
    label = screen.ids.countdown_label
    # Change the text
    label.text = 'Photo\n%d of %d' % (total - count + 1, total)

def change_countdown(timer):
    # Get the widget
    screen = globals_.scr_manager.get_screen('photobooth_sequence')
    img = screen.ids.countdown_img
    # Change the image
    img.source = 'img/%s.png' % str(timer)

def take_photo_pause(seconds):
    # Sleep for required time unless screen changes (stop button press)
    for i in range(10):
        sleep(0.1)
        # Check if the screen has changed (stop button has been pressed)
        if globals_.scr_manager.current != 'photobooth_sequence':
        	flash_brightness(0) # Turn the flash off
        	return True # To exit the photo sequence
    return False # To continue with the photo sequence

def take_photo():
    '''
    Starts the timer and takes a series of photos to be saved.
    '''
    global camera
    # The stream variable to hold the camera data
    stream = io.BytesIO()
    # Get the settings object for the counter and timer
    settings = main.App.get_running_app().config
    # Set the photo counter to the current setting
    counter = settings.getint('Camera', 'photo_count')
    # Turn on pre-flash
    flash_brightness(settings.getint('Camera', 'pre_flash'))
    # Count the number of photos to take
    while counter > 0:
        stream.seek(0)
        # Update the photo counter on screen
        change_photo_count(counter, settings.getint('Camera', 'photo_count'))
        # Reset the countdown timer for next photo
        timer = settings.getint('Camera', 'photo_timer')
        # The countdown
        while timer > 0:
            # Display the timer countdown
            change_countdown(timer)
            if take_photo_pause(1):
                return
            timer = timer - 1
        # Show me random cheese
        change_countdown('cheese{0}'.format(randint(1, 2)))
        # Delay for extra second
        if take_photo_pause(1):
            return
        # Turn the flash on full
        flash_brightness(100)
        # Take the photo
        timestamp = datetime.now()
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S.%f")
        try:
            camera.capture(stream, format='jpeg')
            print 'Photo taken'
        except:
            print 'Error: Could not take photo'

        # Convert to PILLOW image
        stream.seek(0)
        image = Image.open(stream)

        # Perform the post processing
        image = flip_image(image)
        image = auto_adjust_brightness_contrast_gamma(image)

        # Save the final photo
        image.save(join(globals_.photo_path,'{0}.jpg'.format(timestamp)))

        # Turn the flash back
        flash_brightness(settings.getint('Camera', 'pre_flash'))
        counter = counter - 1
        # Delay by a second in between photos
        if take_photo_pause(1):
            return
        # Create thumbnail of image just taken
        threading.Thread(target=create_thumbnail, args=(globals_.photo_path, '{0}.jpg'.format(timestamp), (400, 240))).start()
        # Start the upload to dropbox
        dropbox_stuff.add_to_upload_queue(globals_.photo_path, '{0}.jpg'.format(timestamp))
    # Turn the flash off if not required
    flash_brightness(0)
    # Change back to photobooth screen ready for another photo
    globals_.scr_manager.current = 'photobooth'
    # Reset the countdown image
    change_countdown('clear')


def enable_camera():
    '''
    Enables the picamera to display the preview window.
    The camera should only be called as a new thread by start_camera_thread().
    '''
    global camera
    if globals_.camera_running:
        return

    try:
        camera = picamera.PiCamera()
        globals_.camera_running = True
        configure_camera()
        main_app = main.App.get_running_app()

        # Create the preview window
        x_offset = 0
        y_offset = 0
        width = 640
        height = 480
        camera.start_preview(fullscreen=False, window=(x_offset, y_offset, width, height))
        print "camera enabled"

        # Keep the preview running while the photobooth screen is current
        while (('photobooth' in main_app.root.current) or ('settings_lite' in main_app.root.current)) and globals_.camera_running:
            sleep(0.1)

        # Screen has exited, shutdown the camera preview
        globals_.camera_running = False
        camera.close()
        print('Camera closed')

    except:
        print "Error: Camera could not be initialised"


def configure_camera():
    '''
    Configures all the camera settings.
    To be called when the camera is enabled.
    '''
    global camera
    main_app = main.App.get_running_app()

    res = main_app.config.get('Camera', 'camera.resolution').split('x')
    camera.resolution = (int(res[0]), int(res[1]))
    camera.sharpness = main_app.config.getint('Camera', 'camera.sharpness')
    camera.contrast = main_app.config.getint('Camera', 'camera.contrast')
    camera.brightness = main_app.config.getint('Camera', 'camera.brightness')
    camera.saturation = main_app.config.getint('Camera', 'camera.saturation')
    if main_app.config.get('Camera', 'camera.iso') == 'auto':
        camera.iso = 0
    else:
        camera.iso = main_app.config.getint('Camera', 'camera.iso')
    if main_app.config.getint('Camera', 'camera.video_stabilization') == 1:
        camera.video_stabilization = True
    else:
        camera.video_stabilization = False
    camera.exposure_compensation = main_app.config.getint('Camera', 'camera.exposure_compensation')
    camera.exposure_mode = main_app.config.get('Camera', 'camera.exposure_mode')
    camera.meter_mode = main_app.config.get('Camera', 'camera.meter_mode')
    camera.awb_mode = main_app.config.get('Camera', 'camera.awb_mode')
    camera.meter_mode = main_app.config.get('Camera', 'camera.meter_mode')
    camera.image_effect = main_app.config.get('Camera', 'camera.image_effect')
    camera.rotation = main_app.config.getint('Camera', 'camera.rotation')
    if main_app.config.getint('Camera', 'camera.hflip') == 1:
        camera.hflip = True
    else:
        camera.hflip = False
    if main_app.config.getint('Camera', 'camera.vflip') == 1:
        camera.vflip = True
    else:
        camera.vflip = False

    print "camera configured"
