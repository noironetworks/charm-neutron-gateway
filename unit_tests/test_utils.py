import contextlib
import io
import os
import logging

import unittest
import yaml

import unittest.mock as mock
from unittest.mock import patch


def load_config():
    '''
    Walk backwords from __file__ looking for config.yaml, load and return the
    'options' section'
    '''
    config = None
    f = __file__
    while config is None:
        d = os.path.dirname(f)
        if os.path.isfile(os.path.join(d, 'config.yaml')):
            config = os.path.join(d, 'config.yaml')
            break
        f = d

    if not config:
        logging.error('Could not find config.yaml in any parent directory '
                      'of %s. ' % __file__)
        raise Exception

    return yaml.safe_load(open(config).read())['options']


def get_default_config():
    '''
    Load default charm config from config.yaml return as a dict.
    If no default is set in config.yaml, its value is None.
    '''
    default_config = {}
    config = load_config()
    for k, v in config.items():
        if 'default' in v:
            default_config[k] = v['default']
        else:
            default_config[k] = None
    return default_config


class CharmTestCase(unittest.TestCase):

    def setUp(self, obj, patches):
        super(CharmTestCase, self).setUp()
        self.patches = patches
        self.obj = obj
        self.test_config = TestConfig()
        self.test_relation = TestRelation()
        self.patch_all()
        self._patches = {}
        self._patches_start = {}

    def patch(self, method):
        if "." in method:
            _m = patch(method)
        else:
            _m = patch.object(self.obj, method)
        mock = _m.start()
        self.addCleanup(_m.stop)
        return mock

    def patch_all(self):
        for method in self.patches:
            if "." in method:
                attr = method.split('.')[-1]
            else:
                attr = method
            setattr(self, attr, self.patch(method))

    def tearDown(self):
        for k, v in self._patches.items():
            v.stop()
            setattr(self, k, None)
        self._patches = None
        self._patches_start = None

    def patch_object(self, obj, attr, name=None, **kwargs):
        """Patch a patchable thing.  Uses mock.patch.object() to do the work.
        Automatically unpatches at the end of the test.

        The mock gets added to the test object (self) using 'name' or the attr
        passed in the arguments.

        :param obj: an object that needs to have an attribute patched.
        :param attr: <string> that represents the attribute being patched.
        :param name: optional <string> name to call the mock.
        :param **kwargs: any other args to pass to mock.patch()
        """
        if obj is None:
            mocked = patch(attr, **kwargs)
        else:
            mocked = patch.object(obj, attr, **kwargs)
        if name is None:
            name = attr
        started = mocked.start()
        self._patches[name] = mocked
        self._patches_start[name] = started
        setattr(self, name, started)


class TestConfig(object):

    def __init__(self):
        self.config = get_default_config()

    def get(self, attr):
        try:
            return self.config[attr]
        except KeyError:
            return None

    def get_all(self):
        return self.config

    def set(self, attr, value):
        if attr not in self.config:
            raise KeyError
        self.config[attr] = value


class TestRelation(object):

    def __init__(self, relation_data={}):
        self.relation_data = relation_data

    def set(self, relation_data):
        self.relation_data = relation_data

    def get(self, attr=None, unit=None, rid=None):
        if attr is None:
            return self.relation_data
        elif attr in self.relation_data:
            return self.relation_data[attr]
        return None


@contextlib.contextmanager
def patch_open():
    """Patch open() to allow mocking both open() itself and the file that is
    yielded.

    Yields the mock for "open" and "file", respectively."""
    mock_open = mock.MagicMock(spec=open)
    mock_file = mock.MagicMock(spec=io.FileIO)

    @contextlib.contextmanager
    def stub_open(*args, **kwargs):
        mock_open(*args, **kwargs)
        yield mock_file

    with patch('builtins.open', stub_open):
        yield mock_open, mock_file
