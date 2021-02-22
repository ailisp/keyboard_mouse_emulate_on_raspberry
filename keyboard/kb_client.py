#!/usr/bin/python3
#
# Fruit2pi Bluetooth keyboard emulation service
# keyboard copy client.
# Reads local key events and forwards them to the btk_server DBUS service
#
import os  # used to all external commands
import sys  # used to exit the script
import dbus
import dbus.service
import dbus.mainloop.glib
import time
import evdev  # used to get input from the keyboard
from evdev import *
import keymap  # used to map evdev input to hid keodes

def list_programs():
    return {'programs': os.listdir(programs_dir)}

def edit_program(name, code):
    with open(os.path.join(programs_dir, name), 'w') as f:
        f.write(code)
    return {'status': 'success'}

def delete_programs(names):
    for name in names:
        f = os.path.join(programs_dir, names)
        if os.path.exists(f):
            os.remove(f)
    return {'status': 'success'}

def set_program(name):
    global current_program
    with open(os.path.join(programs_dir, name)) as f:
        program = f.read()
        current_program = {'name': name, 'program': program}
    return {'status': 'success'}
    

def process_command(data):
    try:
        cmds = loads(data)
    except:
        return {'error': 'parse'}
    if type(cmds) != list or not cmds:
        return {'error': 'format'}
    cmd = cmds[0]
    args = cmds[1:]
    if cmd == 'list':
        return list_programs()
    elif cmd == 'edit':
        if len(args) != 2:
            return {'error': 'format'}
        name = args[0]
        code = args[1]
        return edit_program(name, code)
    elif cmd == 'delete':
        if not args:
            return {'error': 'format'}
        return delete_programs(args)
    elif cmd == 'set':
        if len(args) != 1:
            return None
        name = args[0]
        return set_program(name)
    else:
        return {'error': 'format'}


fruit2pi = None
current_program = {'name': 'default', 'program': 'fruit2pi.send(event)'}


# Define a client to listen to local key events
class Keyboard():

    def __init__(self):
        # the structure for a bt keyboard input report (size is 10 bytes)

        self.state = [
            0xA1,  # this is an input report
            0x01,  # Usage report = Keyboard
            # Bit array for Modifier keys
            [0,  # Right GUI - Windows Key
             0,  # Right ALT
             0,  # Right Shift
             0,  # Right Control
             0,  # Left GUI
             0,  # Left ALT
             0,  # Left Shift
             0],  # Left Control
            0x00,  # Vendor reserved
            0x00,  # rest is space for 6 keys
            0x00,
            0x00,
            0x00,
            0x00,
            0x00]

        print("setting up DBus Client")

        self.bus = dbus.SystemBus()
        self.btkservice = self.bus.get_object(
            'org.fruit2pi.btkbservice', '/org/fruit2pi/btkbservice')
        self.iface = dbus.Interface(self.btkservice, 'org.fruit2pi.btkbservice')
        global fruit2pi
        fruit2pi = self
        print("waiting for keyboard")
        # keep trying to key a keyboard
        have_dev = False
        while have_dev == False:
            try:
                # try and get a keyboard - should always be event0 as
                # we're only plugging one thing in
                self.dev = InputDevice("/dev/input/event0")
                have_dev = True
            except OSError:
                print("Keyboard not found, waiting 3 seconds and retrying")
                time.sleep(3)
            print("found a keyboard")

    def change_state(self, event):
        evdev_code = ecodes.KEY[event.code]
        modkey_element = keymap.modkey(evdev_code)

        if modkey_element > 0:
            if self.state[2][modkey_element] == 0:
                self.state[2][modkey_element] = 1
            else:
                self.state[2][modkey_element] = 0
        else:
            # Get the keycode of the key
            hex_key = keymap.convert(ecodes.KEY[event.code])
            # Loop through elements 4 to 9 of the inport report structure
            for i in range(4, 10):
                if self.state[i] == hex_key and event.value == 0:
                    # Code 0 so we need to depress it
                    self.state[i] = 0x00
                elif self.state[i] == 0x00 and event.value == 1:
                    # if the current space if empty and the key is being pressed
                    self.state[i] = hex_key
                    break
        return self.state

    # poll for keyboard events
    def event_loop(self):
        global current_program
        while True:
            try:
                for event in self.dev.read_loop():
                    # only bother if we hit a key and its an up or down event
                    if event.type == ecodes.EV_KEY and event.value < 2:
                        event = self.change_state(event)
                        eval(current_program['program'])
            except BaseException as e:
                print('An error occurred:', file=sys.stderr)
                print(e.__repr__(), file=sys.stderr)

    # forward keyboard events to the dbus service
    def send(self, event):
        bin_str = ""
        state = event
        print(*state)
        element = state[2]
        for bit in element:
            bin_str += str(bit)
        self.iface.send_key(int(bin_str, 2), self.state[4:10])


if __name__ == "__main__":
    print("Setting up keyboard")
    kb = Keyboard()

    print("starting event loop")
    kb.event_loop()
