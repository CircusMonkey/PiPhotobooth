"""
PiPhotobooth
"""
'''
#-------------------------------------------#
#-- Stuff TODO -----------------------------#
#-------------------------------------------#

Proper dropbox login flow

USB and memorycard selection support

post processing of images - gamma, saturation and brightness

'''

'''
#-------------------------------------------#
#-- Import Modules -------------------------#
#-------------------------------------------#
'''
from os.path import join, dirname, expanduser
from subprocess import Popen, call, PIPE
import re
import signal
import sys
from time import sleep

# Kivy modules
import os
os.environ['KIVY_GL_BACKEND'] = 'gl' # Fix for segfault on raspbian stretch
from kivy.app import App
from kivy.uix.settings import SettingsWithSidebar
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.button import Button
from kivy.logger import Logger
from kivy.lang import Builder
from kivy.core.window import Window
from kivy.config import Config
Config.set('kivy', 'keyboard_mode', 'systemandmulti')

# Import custom modules
import globals_
from camera_stuff import *
from photoviewer import *
import dropbox_stuff



'''
#-------------------------------------------#
#-- GUI Stuff ------------------------------#
#-------------------------------------------#
'''

class Main(App):
    # Display the kivy tab in the settings. Disable when not developing.
    use_kivy_settings = False

    def build(self):
        '''
        Build and return the root widget.
        '''
        self.settings_cls = SettingsWithSidebar

        # Load the main screens kv file
        Builder.load_file(join(dirname(__file__), 'screens.kv'))

        # Add all the screens to the screen manager
        globals_.scr_manager = ScreenManager()
        globals_.scr_manager.add_widget(MainMenuScreen(name='mainmenu'))
        globals_.scr_manager.add_widget(PhotoboothScreen(name='photobooth'))
        globals_.scr_manager.add_widget(PhotoboothSequenceScreen(name='photobooth_sequence'))
        globals_.scr_manager.add_widget(PhotoviewerScreen(name='photoviewer'))
        globals_.scr_manager.add_widget(SinglePhotoScreen(name='singlephoto'))
        globals_.scr_manager.add_widget(SettingsLiteScreen(name='settings_lite'))
        globals_.scr_manager.add_widget(SettingsLiteSliderScreen(name='settings_lite_slider'))
        globals_.scr_manager.add_widget(SettingsLiteOptionsScreen(name='settings_lite_options'))

        # Adjust the transition time for user experience
        globals_.scr_manager.transition.duration = 0.2

        # Init the PWM mode for the camera flash
        pin = 21
        init_pwm(pin)

        threading.Thread(target=dropbox_stuff.sync_check, args=(60,)).start()

        return globals_.scr_manager

    def build_config(self, config):
        '''
        Set the default values for the configs sections.
        '''
        config.setdefaults('Camera', {'photo_count': 3,
                                      'photo_timer': 5,
                                      'flash_enabled': '1',
                                      'pre_flash': 20,
                                      'flash_always_on': '0',
                                      'camera.resolution':'1920x1080',
                                      'camera.sharpness':0,
                                      'camera.contrast':0,
                                      'camera.brightness':50,
                                      'camera.saturation':0,
                                      'camera.iso':0,
                                      'camera.video_stabilization':'0',
                                      'camera.exposure_compensation':0,
                                      'camera.exposure_mode':'auto',
                                      'camera.meter_mode':'average',
                                      'camera.awb_mode':'auto',
                                      'camera.image_effect':'none',
                                      'camera.rotation':'0',
                                      'camera.hflip':'1',
                                      'camera.vflip':'0'})
        config.setdefaults('Web',    {'wifi_ssid': 'Alloutofgum',
                                      'wifi_pass': 'TacoTuesday49',
                                      'event_name': "Jess and Sams Wedding"})


    def build_settings(self, settings):
        '''
        Adds custom settings panel to the default configuration object.
        '''
        settings.add_json_panel('Camera', self.config, join(dirname(__file__), 'camera.json'))
        settings.add_json_panel('Web', self.config, join(dirname(__file__), 'web.json'))

    def on_config_change(self, config, section, key, value):
        '''
        Respond to changes in the configuration.
        '''
        Logger.info("main.py: App.on_config_change: {0}, {1}, {2}, {3}".format(config, section, key, value))

        # Turn the flash on if required
        if (key == 'flash_always_on'):
            if (value == '1'):
                flash_brightness(config.getint('Camera', 'pre_flash'))
            elif (value == '0'):
                flash_brightness(0)

        # Change the wifi config file if required
        elif (key == 'wifi_ssid'):
            self.change_ssid(value)
        elif (key == 'wifi_pass'):
            self.change_wifi_pass(value)

        # Refresh the link and qrcode to dropbox
        elif (key == 'event_name'):
            value = re.sub('[^A-z0-9 ]+', '', value)
            config.set(section, key, value)
            threading.Thread(target=event_change, args=(value,)).start()


    def close_settings(self, settings):
        '''
        The settings panel has been closed.
        '''
        Logger.info("main.py: App.close_settings: {0}".format(settings))
        super(Main, self).close_settings(settings)



    '''
    #-------------------------------------------#
    #-- OS Stuff -------------------------------#
    #-------------------------------------------#
    '''
    def reboot(self):
        '''
        Reboot the raspberry pi
        '''
        command = "/usr/bin/sudo /sbin/shutdown -r now"
        process = Popen(command.split(), stdout=PIPE)
        output = process.communicate()[0]
        print(output)

    def shutdown(self):
        '''
        Shutdown the raspberry pi gracefully
        '''
        command = "/usr/bin/sudo /sbin/shutdown -h now"
        process = Popen(command.split(), stdout=PIPE)
        output = process.communicate()[0]
        print(output)

    def change_ssid(self, new_ssid):
        '''
        Changes the configuration file /etc/wpa_supplicant/wpa_supplicant.conf
        to a new SSID name.
        '''
        # Read the file. Needs to be a sudo read :(
        command = "/usr/bin/sudo cat /etc/wpa_supplicant/wpa_supplicant.conf"
        process = Popen(command.split(), stdout=PIPE)
        text = process.communicate()[0]
        # Search the text and insert the new SSID
        matches = re.findall(r'ssid="(.*)"', text)
        text = re.sub(matches[0], new_ssid, text)

        # Write back to a new file
        self.update_system_file('/etc/wpa_supplicant/wpa_supplicant.conf', text)

    def change_wifi_pass(self, new_pass):
        '''
        Changes the configuration file /etc/wpa_supplicant/wpa_supplicant.conf
        to a new password.
        '''
        # Read the file. Needs to be a sudo read :(
        command = "/usr/bin/sudo cat /etc/wpa_supplicant/wpa_supplicant.conf"
        process = Popen(command.split(), stdout=PIPE)
        text = process.communicate()[0]
        # Search the text and insert the new password
        matches = re.findall(r'psk="(.*)"', text)
        text = re.sub(matches[0], new_pass, text)

        # Write back to a new file
        self.update_system_file('/etc/wpa_supplicant/wpa_supplicant.conf', text)


    def update_system_file(self, file_path, text):
        '''
        Creates a temp file, removes original file, then renames temp file.
        Better make sure you're using it right!
        '''
        with open(join(expanduser('~'), 'temp.txt'), 'w') as f:
            f.write(text)
            f.close()

        # Clone the ownership and permissions to the temp file
        command = "/usr/bin/sudo chown --reference={0} /home/pi/temp.txt".format(file_path)
        process = Popen(command.split(), stdout=PIPE)
        output = process.communicate()[0]
        command = "/usr/bin/sudo chmod --reference={0} /home/pi/temp.txt".format(file_path)
        process = Popen(command.split(), stdout=PIPE)
        output = process.communicate()[0]

        # Rename existing file to backup
        command = "/usr/bin/sudo mv {0} {0}.backup".format(file_path)
        process = Popen(command.split(), stdout=PIPE)
        output = process.communicate()[0]

        # Rename temp file to original name
        command = "/usr/bin/sudo mv /home/pi/temp.txt {0}".format(file_path)
        process = Popen(command.split(), stdout=PIPE)
        output = process.communicate()[0]

        
class MainMenuScreen(Screen):
    def on_enter(self):
        # Load the event details when started
        # (to respond to a direct .ini settings change
        # when I change it manually and not by the interface)
        settings = main.App.get_running_app().config
        event = settings.get('Web', 'event_name')
        threading.Thread(target=event_change, args=(event,)).start()

        
def event_change(event):
    # Change the photo folder
    globals_.photo_path = join(dirname(__file__), 'photos', event)
    # Check for directory
    if not exists(globals_.photo_path):
        makedirs(globals_.photo_path)
        
    # Generate a new dropbox link and qrcode
    url = dropbox_stuff.get_shared_link(globals_.dbx, event)
    print('New url: %s' % url)
    create_qr_code(url)


def signal_handler(signal, frame):
    globals_.shutdown_request = True
    globals_.camera_running = False
    sleep(1)
    stop_pwm()
    print('Closed gracefully. Bye Bye!')
    sys.exit(0)


if __name__ == "__main__":
    # Register the signal handler to close gracefully using ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    # Start the main app
    Main().run()
