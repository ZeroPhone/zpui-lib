import os

from zpui_lib.helpers import setup_logger
logger = setup_logger(__name__)

beepy_dir = "/sys/firmware/beepy/"

preset_device = None
known_devices = ["snowdive", "blepis", "beepy", "colorberry"]

# a few colors for the onboard LED
colors = {
  "red":              (10,  0,  0),
  "green":            ( 0, 10,  0),
  "blue":             ( 0,  0, 10),
  "purple":           (10,  0, 10),
  "orange":           (15,  5,  0),
  "safety-orange":    (15,  2,  0),
  "sea":              ( 0, 10,  5),
  "emerald":          ( 0, 10,  2),
  "yellow":           (15, 10,  0),
  "magenta":          (15,  0,  2),
  "pink":             (15,  0,  5),
  "salmon":           (15,  5,  5),
  "off":              ( 0,  0,  0),
}

def detect_device():
    """Able to distinguish between snowdive/blepis/beepy - in the future."""
    if preset_device != None:
        return preset_device
    raise NotImplementedError("Device recognition capability not available yet: please use set_device('your device name') first!")

def set_device(device):
    """A temporary function to set the device, likely, from the ZPUI config"""
    global preset_device
    if device not in known_devices:
        logger.warning(f"Device {device} not known to the current version of the library!")
    preset_device = device
    return device in known_devices

def set_device_from_platform(platform):
    if "snowdive" in platform:
        set_device("snowdive")
        return "snowdive"
    elif "blepis" in platform:
        set_device("blepis")
        return "blepis"
    elif "colorberry" in platform:
        set_device("colorberry")
        return "colorberry"
    else:
        set_device("beepy")
        return "beepy"

def driver_loaded():
    """
    Simple detection, seeing whether the sysfs directory is present
    """
    return os.path.isdir(beepy_dir)

# There are more known capabilities than these, but, hey
known_capabilities = {
    "usb_keyboard_mouse":["usb_keyboard", "usb_mouse"],
    "battery":["battery_percent", "battery_volts", "battery_raw"],
    "led":["led_blue", "led_red", "led_green", "led"],
    "charger":["charger_enabled", "charger_power"],
    "gpio":["gpio_dir", "gpio_value"],
    "display_backlight":None,
    "keyboard_backlight":None,
    "mux_fusb":None,
    "mux_usb":None,
    "mux_uart":None,
    "vibromotor":None,
    "fw_version":None,
    "keyboard_freq":None,
    "rewake_timer":None,
    "fw_update":None,
    "last_keypress":None,
    "startup_reason":None,
}

def get_capabilities():
    """
    Returns a list of things the driver is able to do.
    Any not-yet-recognized entries in sysfs are added to the list.
    """
    # battery_percent  battery_volts    charger_power  fw_version  gpio_value          keyboard_freq
    # lcd_backlight  led_blue   led_red   mux_uart  rewake_timer    usb_keyboard  vibromotor
    # battery_raw      charger_enabled  fw_update      gpio_dir    keyboard_backlight  last_keypress
    # led            led_green  mux_fusb  mux_usb   startup_reason  usb_mouse
    capabilities = []
    sysfs_files = os.listdir(beepy_dir)
    for name, files in known_capabilities.items():
        files = [name] if files == None else files # handles None as value
        files_present = all(file in sysfs_files for file in files)
        if files_present:
            capabilities.append(name)
            for file in files:
                sysfs_files.remove(file)
    # what's left in sysfs, gets added too, but with a warning!
    for file in sysfs_files:
        logger.warning(f"Yet unrecognized driver capability '{file}', beepy library needs an update")
        capabilities.append(file)
    return capabilities



"""
LED functions
"""

def led_write_rawlednum(r, g, b, rawleds):
    """
    Works like led_write, except it expects raw LED numbers. Currently, only this function allows you to enable blinking for LED 0.
    """
    if not isinstance(rawleds, (list, tuple)):
        rawleds = [rawleds]
    try:
        with open(beepy_dir+"led_red", 'w') as f:
            f.write(str(r))
        with open(beepy_dir+"led_green", 'w') as f:
            f.write(str(g))
        with open(beepy_dir+"led_blue", 'w') as f:
            f.write(str(b))
        for led in rawleds:
            with open(beepy_dir+"led", 'w') as f:
                f.write(str(led))
    except:
        logger.exception("Error while writing to sysfs LED files!")
        return False
    else:
        return True

def led_write(r, g, b, leds):
    """
    Puts LED colors into sysfs files. Can set multiple LEDs at a time - just pass the list of LEDs you want set instead of a number.
    """
    if not isinstance(leds, (list, tuple)):
        leds = [leds]
    enable_bit = not (r==0 and g==0 and b==0)
    # conversion into bits = led0 is 0/1, led1 is 4, led2 is 8, led3 is 12
    rawleds = [enable_bit+(led<<2)for led in leds]
    return led_write_rawlednum(r, g, b, rawleds)

def led_clear(leds):
    """Small stub for a tiny bit of user-friendliness"""
    return led_write(0,0,0,leds)

def get_led_amount(device=None):
    """
    This requires device detection
    """
    if device == None:
        device = detect_device()
    if device == "snowdive":
        return 4
    elif device == "blepis":
        return 2
    else: # beepy, colorberry, other ones
        return 1

