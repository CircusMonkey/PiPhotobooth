'''
#-------------------------------------------#
#-- Global Stuff ---------------------------#
#-------------------------------------------#
'''

from os.path import join, dirname
import threading
import dropbox

from dropbox_stuff import dropbox_login

# Root screen manager for navigation
global scr_manager

# Current setting from json file
cur_setting = {}

# The PWM pin object tied to the camera flash
global flash

# Path to photos. To be changed to mem card or usb.
photo_path = ""

# Is the camera running
camera_running = False

# Has a shutdown been requested? Used by threads to terminate.
shutdown_request = False

# List to track progress of dropbox uploads
queue = []
mutex = False

# Dropbox login
logged_on = False;
threading.Thread(target=dropbox_login, args=()).start()
