#!/usr/bin/env python3

import os
import sys

_path = os.path.dirname(os.path.realpath(__file__))
_hooks_dir = os.path.abspath(os.path.join(_path, "..", "hooks"))


def _add_path(path):
    if path not in sys.path:
        sys.path.insert(1, path)


_add_path(_hooks_dir)


from charmhelpers.core.hookenv import action_fail
from neutron_utils import (
    pause_unit_helper,
    resume_unit_helper,
    register_configs,
)


def pause(args):
    """Pause the Ceilometer services.
    @raises Exception should the service fail to stop.
    """
    pause_unit_helper(register_configs())


def resume(args):
    """Resume the Ceilometer services.
    @raises Exception should the service fail to start."""
    resume_unit_helper(register_configs())


# A dictionary of all the defined actions to callables (which take
# parsed arguments).
ACTIONS = {"pause": pause, "resume": resume}


def main(args):
    action_name = os.path.basename(args[0])
    try:
        action = ACTIONS[action_name]
    except KeyError:
        s = "Action {} undefined".format(action_name)
        action_fail(s)
        return s
    else:
        try:
            action(args)
        except Exception as e:
            action_fail("Action {} failed: {}".format(action_name, str(e)))


if __name__ == "__main__":
    sys.exit(main(sys.argv))
