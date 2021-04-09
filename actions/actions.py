#!/usr/bin/env python3

import os
import sys

_path = os.path.dirname(os.path.realpath(__file__))
_hooks_dir = os.path.abspath(os.path.join(_path, "..", "hooks"))


def _add_path(path):
    if path not in sys.path:
        sys.path.insert(1, path)


_add_path(_hooks_dir)


import charmhelpers.contrib.openstack.utils as os_utils
from charmhelpers.core.hookenv import (
    DEBUG,
    action_get,
    action_fail,
    log,
)
from neutron_utils import (
    assess_status,
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


def restart(args):
    """Restart services.

    :param args: Unused
    :type args: List[str]
    """
    deferred_only = action_get("deferred-only")
    services = action_get("services").split()
    # Check input
    if deferred_only and services:
        action_fail("Cannot set deferred-only and services")
        return
    if not (deferred_only or services):
        action_fail("Please specify deferred-only or services")
        return
    if action_get('run-hooks'):
        log("Charm does not defer any hooks at present", DEBUG)
    if deferred_only:
        os_utils.restart_services_action(deferred_only=True)
    else:
        os_utils.restart_services_action(services=services)
    assess_status(register_configs())


def run_deferred_hooks(args):
    """Run deferred hooks.

    :param args: Unused
    :type args: List[str]
    """
    # Charm defers restarts on a case-by-case basis so no full
    # hook deferalls are needed.
    action_fail("Charm does not defer any hooks at present")


def show_deferred_events(args):
    """Show the deferred events.

    :param args: Unused
    :type args: List[str]
    """
    os_utils.show_deferred_events_action_helper()


# A dictionary of all the defined actions to callables (which take
# parsed arguments).
ACTIONS = {"pause": pause, "resume": resume, "restart-services": restart,
           "show-deferred-events": show_deferred_events,
           "run-deferred-hooks": run_deferred_hooks}


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
