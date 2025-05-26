import psutil
import os
import sys

import unittest

def local_path_gen(_name_):
    """This function generates a ``local_path`` function you can use
    in your scripts to get an absolute path to a file in your app's
    directory. You need to pass ``__name__`` to ``local_path_gen``. Example usage:

    .. code-block:: python

        from zpui_lib.helpers import local_path_gen
        local_path = local_path_gen(__name__)
        ...
        config_path = local_path("config.json")

    The resulting local_path function supports multiple arguments,
    passing all of them to ``os.path.join`` internally."""
    app_path = os.path.dirname(sys.modules[_name_].__file__)

    def local_path(*path):
        return os.path.join(app_path, *path)
    return local_path

def get_safe_file_backup_path(dir, fname, new_dir = None, word="old"):
    """This function lets you safely backup a user's file that you want to move.
    It does this by adding an integer suffix to the target filename,
    and increments that suffix until it's assured that the move target path does not yet exist,
    as long as necessary. This ensures that, whatever file you move, there's always a backup.
    This function is extension-sensitive - it will try its best to take good care of the file extension.

    You can pass a new directory for the file to be saved into.
    """
    if not new_dir: new_dir = dir
    def get_fn_ext(num): # default function for files without extension
        nonlocal name, ext
        return "{}_{}{}.{}".format(name, word, num, ext)
    def get_fn(num): # default function for files without extension
        nonlocal fname
        return "{}_{}{}".format(fname, word, num)
    fname_els = fname
    if '.' in fname: # file has an extension
        if fname.endswith("tar.gz"):
            name, ext, ext2 = fname.rsplit('.', 2)
            ext = ext+'.'+ext2
        else:
            name, ext = fname.rsplit('.', 1)
        get_fn = get_fn_ext
    current_path = os.path.join(dir, fname)
    i = 1
    new_fname = get_fn(i)
    while new_fname in os.listdir(new_dir):
        i += 1
        new_fname = get_fn(i)
    new_path = os.path.join(new_dir, new_fname)
    return current_path, new_path

def flatten(foo, restrict=None):
    if restrict == None: restrict = []
    if foo in restrict:
        return foo
    for x in foo:
        if hasattr(x, '__iter__') and x not in restrict:
            for y in flatten(x):
                yield y
        else:
            yield x


# noinspection PyTypeChecker,PyArgumentList
class Singleton:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not isinstance(cls._instance, cls):
            cls._instance = object.__new__(cls)
        return cls._instance

class TestGeneralHelpers(unittest.TestCase):

    def test_flatten(self):
        """tests that it runs when a device isn't provided"""
        f = flatten([[1, 1, 1, 0], [1, 1, 1, 0], [1, 1, 1, 0], [1, 1, 1, 0]])
        assert(list(f) == [1, 1, 1, 0, 1, 1, 1, 0, 1, 1, 1, 0, 1, 1, 1, 0])
        f = flatten([[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]])
        assert(list(f) == [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])

    def test_local_path_gen(self):
        local_path = local_path_gen(__name__)
        assert(local_path("general.py").endswith("general.py"))

    def test_gsfbp(self):
        new_paths = []
        test_dir = "/tmp/"
        fname = "zpui_sbf_test_fname"
        for i in range(10):
            # call the function 10 times
            path = os.path.join(test_dir, fname)
            with open(path, "w") as f:
                f.write(str(i))
            old_path, new_path = get_safe_file_backup_path(test_dir, fname)
            os.rename(old_path, new_path)
        files = os.listdir(test_dir)
        for file in files:
            print(file)
        for i in range(1, 11):
            # check that the files are there
            path = "{}_old{}".format(fname, i)
            print(path)
            assert(path in files)
            os.remove(os.path.join(test_dir, path))

    def test_gsfbp_ext(self):
        new_paths = []
        test_dir = "/tmp/"
        fname = "zpui_sbf_test_fname.txt"
        name = "zpui_sbf_test_fname"
        for i in range(10):
            # call the function 10 times
            path = os.path.join(test_dir, fname)
            with open(path, "w") as f:
                f.write(str(i))
            old_path, new_path = get_safe_file_backup_path(test_dir, fname)
            os.rename(old_path, new_path)
        files = os.listdir(test_dir)
        for file in files:
            print(file)
        for i in range(1, 11):
            # check that the files are there
            path = "{}_old{}.txt".format(name, i)
            print(path)
            assert(path in files)
            os.remove(os.path.join(test_dir, path))

if __name__ == "__main__":
    unittest.main()
