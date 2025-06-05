import psutil
import os

emulator_flag_filename = "emulator"

from zpui_lib.helpers.logger import setup_logger
logger = setup_logger(__name__, "warning")

def zpui_running_as_service():
    if psutil.Process(os.getpid()).ppid() == 1:
        return True
    else:
        return False

def is_emulator():
    # assumes it's loaded in ZPUI context, of course
    # will have to be rewritten once apps are no longer loaded in ZPUI context
    return emulator_flag_filename in os.listdir(".")

def is_beepy():
    return os.path.exists("/sys/firmware/beepy/")

def get_platform():
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
    return platform_info

if __name__ == "__main__":
    print(get_platform())
