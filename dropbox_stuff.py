"""

"""

from __future__ import print_function

import globals_

import argparse
import contextlib
import datetime
import os
import six
import sys
import time
import unicodedata
import re
from time import sleep
import threading


if sys.version.startswith('2'):
    input = raw_input

import dropbox
from dropbox.files import FileMetadata, FolderMetadata
from dropbox.sharing import PendingUploadMode

import main

'''
Keeps trying to login to dropbox until successful
'''
def dropbox_login():
    token = "your_dropbox_token"
    globals_.dbx = dropbox.Dropbox(token)

'''
Gets the shared link to the dropbox folder
'''
def get_shared_link(dbx, path):
    path = re.sub('[^A-z0-9 ]+', '', path)
    while True:
        try:
            shared_link_metadata = dbx.sharing_create_shared_link('/%s' % path, short_url=True, pending_upload=PendingUploadMode.folder)
            globals_.logged_on = True
            print('Dropbox link %s aquired' % shared_link_metadata.url)
            return shared_link_metadata.url
        except:
            print('Dropbox link failed. Retrying in 5 seconds.')
            sleep(5)


def list_folder(dbx, folder, subfolder):
    """List a folder.
    Return a dict mapping unicode filenames to
    FileMetadata|FolderMetadata entries.
    """
    path = '/%s/%s' % (folder, subfolder.replace(os.path.sep, '/'))
    while '//' in path:
        path = path.replace('//', '/')
    path = path.rstrip('/')
    try:
        with stopwatch('checking dropbox directory listing'):
            res = dbx.files_list_folder(path)
    except dropbox.exceptions.ApiError as err:
        print('Folder listing failed for', path, '-- assumped empty:', err)
        return {}
    else:
        rv = {}
        for entry in res.entries:
            rv[entry.name] = entry
        return rv

def download(dbx, folder, subfolder, name):
    """Download a file.
    Return the bytes of the file, or None if it doesn't exist.
    """
    path = '/%s/%s/%s' % (folder, subfolder.replace(os.path.sep, '/'), name)
    while '//' in path:
        path = path.replace('//', '/')
    with stopwatch('download'):
        try:
            md, res = dbx.files_download(path)
        except dropbox.exceptions.HttpError as err:
            print('*** HTTP error', err)
            return None
    data = res.content
    print(len(data), 'bytes; md:', md)
    return data

def upload(dbx, fullname, folder, subfolder, name, overwrite=False):
    """Upload a file.
    Return the request response, or None in case of error.
    """
    path = '/%s/%s/%s' % (folder, subfolder.replace(os.path.sep, '/'), name)
    while '//' in path:
        path = path.replace('//', '/')
    mode = (dropbox.files.WriteMode.overwrite
            if overwrite
            else dropbox.files.WriteMode.add)
    mtime = os.path.getmtime(fullname)
    with open(fullname, 'rb') as f:
        data = f.read()
    with stopwatch('upload %s (%d bytes)' % (name, len(data))):
        try:
            res = dbx.files_upload(
                data, path, mode,
                client_modified=datetime.datetime(*time.gmtime(mtime)[:6]),
                mute=True)
        except dropbox.exceptions.ApiError as err:
            print('*** API error', err)
            return None
    print('Uploaded as', res.name.encode('utf8'))
    return res

'''
Uploads the file to dropbox via the APIv2
'''
def run_dropbox_upload():
    # Wait until dropbox is active
    while (globals_.logged_on == False):
        if globals_.shutdown_request:
            return
        print('Dropbox not logged in. Retrying in 10 seconds.')
        sleep(10)

    settings = main.App.get_running_app().config
    while len(globals_.queue) > 0:
        path = globals_.queue[0][0]
        filename = globals_.queue[0][1]
        print('Uploading %s' % filename)
        try:
            upload(globals_.dbx, os.path.join(path, filename), settings.get('Web', 'event_name'), '', filename, overwrite=True)
            # Wait for the queue to be released
            while globals_.mutex:
                sleep(0.1)
            globals_.mutex = True # Aquire mutex lock
            globals_.queue.pop(0) # Remove from queue
            globals_.mutex = False # Release the lock
            print('Photo %s Successfully uploaded' % filename)
            print('Upload queue length: %i' % len(globals_.queue))
        except:
            print('Photo %s upload failed. Retrying in 10s' % filename)
            sleep(10)
    # All uploaded... or is it?


# Check that the photos are all sunk
def sync_check(delay):

    # Loop about every minute. Check that all photos have been uploaded
    while True:
        count = 0
        while count < delay:
            count = count + 1
            time.sleep(1)
            if globals_.shutdown_request:
                return

        if len(globals_.queue) == 0:
            print('Checking sync status')
            settings = main.App.get_running_app().config

            listing = list_folder(globals_.dbx, settings.get('Web', 'event_name'), '')

            files = [f for f in os.listdir(globals_.photo_path) if os.path.isfile(os.path.join(globals_.photo_path, f))]
            for name in files:
                # Do all the files - ignores folders
                fullname = os.path.join(globals_.photo_path, name)
                if not isinstance(name, six.text_type):
                    name = name.decode('utf-8')
                nname = unicodedata.normalize('NFC', name)
                if name.startswith('.') or name.startswith('@') or name.endswith('~') or name.endswith('.pyc') or name.endswith('.pyo'):
                    pass
                elif nname in listing:
                    md = listing[nname]
                    mtime = os.path.getmtime(fullname)
                    mtime_dt = datetime.datetime(*time.gmtime(mtime)[:6])
                    size = os.path.getsize(fullname)
                    if (isinstance(md, dropbox.files.FileMetadata) and
                        mtime_dt == md.client_modified and size == md.size):
                        pass
                    else:
                        # Metadata does not match
                        add_to_upload_queue(globals_.photo_path, name)
                else:
                    # File doesn't exist on dropbox
                    add_to_upload_queue(globals_.photo_path, name)



def add_to_upload_queue(path, filename):
    # Wait for the queue to be released
    while globals_.mutex:
        sleep(0.01)
    globals_.mutex = True # Aquire mutex lock
    globals_.queue.append([path, filename])
    if len(globals_.queue) == 1:
        threading.Thread(target=run_dropbox_upload, args=()).start()
    print('Photo %s added to queue' % filename)
    print('Upload queue length: %i' % len(globals_.queue))
    globals_.mutex = False # Release the lock

@contextlib.contextmanager
def stopwatch(message):
    """Context manager to print how long a block of code took."""
    t0 = time.time()
    try:
        yield
    finally:
        t1 = time.time()
        print('Total elapsed time for %s: %.3f' % (message, t1 - t0))
