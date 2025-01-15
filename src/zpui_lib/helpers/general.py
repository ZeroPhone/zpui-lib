import psutil
import os
import sys

def local_path_gen(_name_):
    """This function generates a ``local_path`` function you can use
    in your scripts to get an absolute path to a file in your app's
    directory. You need to pass ``__name__`` to ``local_path_gen``. Example usage:

    .. code-block:: python

        from helpers import local_path_gen
        local_path = local_path_gen(__name__)
        ...
        config_path = local_path("config.json")

    The resulting local_path function supports multiple arguments,
    passing all of them to ``os.path.join`` internally."""
    app_path = os.path.dirname(sys.modules[_name_].__file__)

    def local_path(*path):
        return os.path.join(app_path, *path)
    return local_path

def safely_backup_file(dir, fname, new_dir = None, fmt = "{0}_old{1}"):
    """This function lets you safely backup a user's file that you want to move.
    It does this by adding an integer suffix to the target filename,
    and increments that suffix until it's assured that the move target path does not yet exist,
    as long as necessary. This ensures that, whatever file you move, there's always a backup.

    You can pass the filename format string to it, (0:old filename, 1:integer),
    as well as a new directory for the file to be saved into.
    """
    if not new_dir: new_dir = dir
    current_path = os.path.join(dir, fname)
    i = 1
    new_fname = fmt.format(fname, i)
    while new_fname in os.listdir(new_dir):
        i += 1
        new_fname = fmt.format(fname, i)
    new_path = os.path.join(new_dir, new_fname)
    os.move(current_path, new_path)
    return new_path

def flatten(foo):
    for x in foo:
        if hasattr(x, '__iter__'):
            for y in flatten(x):
                yield y
        else:
            yield x


# noinspection PyTypeChecker,PyArgumentList
class Singleton(object):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not isinstance(cls._instance, cls):
            cls._instance = object.__new__(cls, *args, **kwargs)
        return cls._instance
