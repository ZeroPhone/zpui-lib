#!/usr/bin/env python2

import json
import os
import shutil
from types import MethodType

from zpui_lib.helpers.logger import setup_logger
logger = setup_logger(__name__, "warning")

yaml = None

try:
    import yaml
except ImportError:
    pass

def read_config(config_path):
    global yaml
    if config_path.endswith(".yaml"):
        if not yaml:
            logger.error("attempted to write {} with {}, but pyyaml library not found!".format(config_path))
            import yaml # raises ImportError
        with open(config_path) as f:
            data = yaml.safe_load(f)
        return data
    else: #if config_path.endswith(".json"):
        with open(config_path) as f:
            data = json.load(f)
        return data

def write_config(config_dict, config_path):
    global yaml
    if config_path.endswith(".yaml"):
        if not yaml:
            logger.error("attempted to write {} with {}, but pyyaml library not found!".format(config_path, config_dict))
            import yaml # raises ImportError
        with open(config_path, 'w') as f:
            yaml.safe_dump(config_dict, f)
    else: #if config_path.endswith(".json"):
        with open(config_path, 'w') as f:
            json.dump(config_dict, f)

def move_faulty_config_to_new_path(config_path, suffix="failed"):
    counter = 1
    new_path = config_path + ".{}".format(suffix)
    while os.path.exists(new_path):
        new_path = config_path + ".{}_{}".format(suffix, counter)
        counter += 1
    shutil.move(config_path, new_path)
    return new_path

def read_or_create_config(config_path, default_config, app_name):
    # type: (str, str, str) -> dict
    """
    reads the config in `config_path` if invalid, replaces it with `default_config` and saves the erroneous config
    in `config_path`.failed. Also, if the config is a dictionary, adds keys to it if
    they're present in the default config but not in the current config.

    >>> print('{"configtype":"sample", "version":1}', file=open('/tmp/a_valid_config_file.json',"w"))
    >>> c = read_or_create_config("/tmp/a_valid_config_file.json", '{"default_config":true}', "test_runner")
    >>> c['configtype']
    'sample'
    >>> c['default_config']
    True

    >>> print('{{{zzz', file=open('/tmp/a_invalid_config_file.json',"w"))
    >>> c = read_or_create_config("/tmp/a_invalid_config_file.json", '{"default_config":true}', "test_runner")
    >>> os.path.exists("/tmp/a_invalid_config_file.json.failed")
    True
    >>> c['default_config']
    True

    >>> print('{{{zzz', file=open('/tmp/a_invalid_config_file.json',"w"))
    >>> c = read_or_create_config("/tmp/a_invalid_config_file.json", '{"default_config":true}', "test_runner")
    >>> os.path.exists("/tmp/a_invalid_config_file.json.failed_1")
    True
    """
    try:
        config_obj = read_config(config_path)
    except (ValueError, OSError) as e:
        if isinstance(e, FileNotFoundError):
            logger.info("{}: config not yet created, creating with defaults...".format(app_name))
        else:
            logger.exception("{}: broken config, restoring with defaults...".format(app_name))
        if os.path.exists(config_path):
            new_path = move_faulty_config_to_new_path(config_path)
            logger.warning("Moved the faulty config file into {}".format(new_path))
        with open(config_path, 'w') as f:
            f.write(default_config)
        config_obj = read_config(config_path)
    if config_path.endswith(".json"):
        default_config_obj = json.loads(default_config)
    elif config_path.endswith(".yaml"):
        default_config_obj = yaml.safe_load(default_config)
    else:
        raise ValueError("Config path {} doesn't end in .json or .yaml, got no clue how to parse the default config!".format(config_path))
    if isinstance(default_config_obj, list) == isinstance(config_obj, dict):
        # Config and default config are different kinds of objects!
        # That probably means we need to deprecate the old config
        logger.warning("{}: config high-level type changed, backing up and upgrading...".format(app_name))
        new_path = move_faulty_config_to_new_path(config_path, suffix="old")
        logger.warning("Moved the outdated config file into {}".format(new_path))
        config_obj = default_config_obj
    keys_added = False
    if isinstance(default_config_obj, dict):
        for key, value in default_config_obj.items():
            if key not in config_obj.keys():
                config_obj[key] = value
                keys_added = True
                logger.debug("Adding key {} (from the default config) to the config for {}!".format(key, app_name))
        if keys_added:
            logger.warning("Added keys from default config to app {} - changes will not be preserved until the next time config is saved!".format(app_name))
    return config_obj

def save_config_gen(path):
    """
    A helper function, generates a "save config" function with the
    config path already set (to decrease verbosity)
    """
    def save_config(config):
        write_config(config, path)
    return save_config

def save_config_method_gen(obj, path, config_attr_name='config'):
    """
    A helper function, generates a "save config" method with the
    config path already set (to decrease verbosity) and the config
    attribute name hard-coded. This is the ``save_config_gen``
    equivalent for class-based apps.
    """
    def method(self):
        write_config(getattr(self, config_attr_name), path)
    return MethodType(method, obj)

if __name__ == "__main__":
    config = read_config("../config.json")
    print(config)
