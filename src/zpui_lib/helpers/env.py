import psutil
import os

emulator_flag_filename = "emulator"

from zpui_lib.helpers.logger import setup_logger
logger = setup_logger(__name__, "warning")

platform_additions = []

def add_platform_device(device_name):
    """ A function to use within ZPUI, to add devices into the output of get_platform. """
    # assumes it's loaded in ZPUI context, of course
    # will have to be rewritten once apps are no longer loaded in ZPUI context
    if device_name not in platform_additions:
        platform_additions.append(device_name)

def zpui_running_as_service():
    """ Checks if ZPUI has been launched by the init process aka PID 1, returning True or False accordingly. """
    return psutil.Process(os.getpid()).ppid() == 1

def is_emulator():
    """ Checks if ZPUI is running in emulator mode, returning True or False accordingly. """
    # assumes it's loaded in ZPUI context, of course
    # will have to be rewritten once apps are no longer loaded in ZPUI context
    return emulator_flag_filename in os.listdir(".")

def is_beepy():
    """ Checks if ZPUI is running on the Beepy, returning True or False accordingly. """
    # currently, checks for the beepy driver being loaded.
    return os.path.exists("/sys/firmware/beepy/")

def get_platform():
    """
    Returns a list of flags that tell about the environment ZPUI is running in.
    For instance, on emulator, it will return ``["emulator"]``, and on Beepy, it will
    return ``["beepy"]``; if it's running as service on Beepy, it will return
    ``["beepy", "service"]``. You can then do platform checks in your code by
    writing code like ``if "beepy" in get_platform()``.
    """
    platform_info = []
    funcs = (
        (is_emulator, "emulator"),
        (is_beepy, "beepy"),
        (zpui_running_as_service, "service"),
    )
    for func, name in funcs:
        try:
            if func():
                platform_info.append(name)
        except:
            logger.exception("platform detection hook {} failed:".format(repr(str)))
    for device_name in platform_additions:
        if device_name not in platform_info:
            platform_info.append(device_name)
    return platform_info

if __name__ == "__main__":
    print(get_platform())
