#!/usr/bin/env python3
import os
import sys

_path = os.path.dirname(os.path.realpath(__file__))
_hooks_dir = os.path.abspath(os.path.join(_path, "..", "hooks"))


def _add_path(path):
    if path not in sys.path:
        sys.path.insert(1, path)


_add_path(_hooks_dir)


from charmhelpers.contrib.openstack.utils import (
    do_action_openstack_upgrade,
)

from neutron_utils import (
    do_openstack_upgrade,
    NEUTRON_COMMON,
)

from neutron_hooks import (
    config_changed,
    resolve_CONFIGS,
)


def openstack_upgrade():
    """Upgrade packages to config-set Openstack version.

    If the charm was installed from source we cannot upgrade it.
    For backwards compatibility a config flag must be set for this
    code to run, otherwise a full service level upgrade will fire
    on config-changed."""

    if do_action_openstack_upgrade(NEUTRON_COMMON,
                                   do_openstack_upgrade,
                                   resolve_CONFIGS()):
        config_changed()


if __name__ == '__main__':
    openstack_upgrade()
