#!/usr/bin/env python3

import os
import socket
import sys

from keystoneauth1 import identity
from keystoneauth1 import session
from neutronclient.v2_0 import client
import yaml

_path = os.path.dirname(os.path.realpath(__file__))
_hooks_dir = os.path.abspath(os.path.join(_path, "..", "hooks"))


def _add_path(path):
    if path not in sys.path:
        sys.path.insert(1, path)


_add_path(_hooks_dir)

from charmhelpers.core.hookenv import (
    relation_get,
    relation_ids,
    related_units,
)

import charmhelpers.contrib.openstack.utils as os_utils
from charmhelpers.core.hookenv import (
    DEBUG,
    action_get,
    action_fail,
    function_set,
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


def get_neutron():
    """Return authenticated neutron client.

    :return: neutron client
    :rtype: neutronclient.v2_0.client.Client
    :raises RuntimeError: Exception is raised if authentication of neutron
        client fails. This can be either because this unit does not have a
        "neutron-plugin-api" relation which should contain credentials or
        the credentials are wrong or keystone service is not available.
    """
    rel_name = "neutron-plugin-api"
    neutron = None

    for rid in relation_ids(rel_name):
        for unit in related_units(rid):
            rdata = relation_get(rid=rid, unit=unit)
            if rdata is None:
                continue

            protocol = rdata.get("auth_protocol")
            host = rdata.get("auth_host")
            port = rdata.get("auth_port")
            username = rdata.get("service_username")
            password = rdata.get("service_password")
            project = rdata.get("service_tenant")
            project_domain = rdata.get("service_domain", "default")
            user_domain_name = rdata.get("service_domain", "default")
            if protocol and host and port \
               and username and password and project:
                auth_url = "{}://{}:{}/".format(protocol,
                                                host,
                                                port)
                auth = identity.Password(auth_url=auth_url,
                                         username=username,
                                         password=password,
                                         project_name=project,
                                         project_domain_name=project_domain,
                                         user_domain_name=user_domain_name)
                sess = session.Session(auth=auth)
                neutron = client.Client(session=sess)
                break

        if neutron is not None:
            break

    if neutron is None:
        raise RuntimeError("Relation '{}' is either missing or does not "
                           "contain neutron credentials".format(rel_name))
    return neutron


def get_network_agents_on_host(hostname, neutron, agent_type=None):
    """Fetch list of neutron agents on specified host.

    :param hostname: name of host on which the agents are running
    :param neutron: authenticated neutron client
    :param agent_type: If provided, filter only agents of selected type
    :return: List of agents matching given criteria
    :rtype: list[dict]
    """
    params = {'host': hostname}
    if agent_type is not None:
        params['agent_type'] = agent_type

    agent_list = neutron.list_agents(**params)["agents"]

    return agent_list


def get_resource_list_on_agents(agent_list,
                                list_resource_function,
                                resource_name):
    """Fetch resources hosted on neutron agents combined into single list.

    :param agent_list: List of agents on which to search for resources
    :type agent_list: list[dict]
    :param list_resource_function: function that takes agent ID and returns
        resources present on that agent.
    :type list_resource_function: Callable
    :param resource_name: filter only resources with given name (e.g.:
        "networks", "routers", ...)
    :type resource_name: str
    :return: List of neutron resources.
    :rtype: list[dict]
    """
    agent_id_list = [agent["id"] for agent in agent_list]
    resource_list = []
    for agent_id in agent_id_list:
        resource_list.extend(list_resource_function(agent_id)[resource_name])
    return resource_list


def clean_resource_list(resource_list, allowed_keys=None):
    """Strip resources of all fields except those in 'allowed_keys.'

    resource_list is a list where each resources is represented as a dict with
    many attributes. This function strips all but those defined in
    'allowed_keys'
    :param resource_list: List of resources to strip
    :param allowed_keys: keys allowed in the resulting dictionary for each
        resource
    :return: List of stripped resources
    :rtype: list[dict]
    """
    if allowed_keys is None:
        allowed_keys = ["id", "status"]

    clean_data_list = []
    for resource in resource_list:
        clean_data = {key: value for key, value in resource.items()
                      if key in allowed_keys}
        clean_data_list.append(clean_data)
    return clean_data_list


def format_status_output(data, key_attribute="id"):
    """Reformat data from the neutron api into human-readable yaml.

    Input data are expected to be list of dictionaries (as returned by neutron
    api). This list is transformed into dict where "id" of a resource is key
    and rest of the resource attributes are value (in form of dictionary). The
    resulting structure is dumped as yaml text.

    :param data: List of dictionaires representing neutron resources
    :param key_attribute: attribute that will be used as a key in the
        result. (default=id)
    :return: yaml string representing input data.
    """
    output = {}
    for entry in data:
        header = entry.pop(key_attribute)
        output[header] = {}
        for attribute, value in entry.items():
            output[header][attribute] = value

    return yaml.dump(output)


def get_routers(args):
    """Implementation of 'show-routers' action."""
    neutron = get_neutron()
    agent_list = get_network_agents_on_host(socket.gethostname(), neutron,
                                            "L3 agent")
    router_list = get_resource_list_on_agents(agent_list,
                                              neutron.list_routers_on_l3_agent,
                                              "routers")

    clean_data = clean_resource_list(router_list,
                                     allowed_keys=["id",
                                                   "status",
                                                   "ha",
                                                   "name"])

    function_set({"router-list": format_status_output(clean_data)})


def get_dhcp_networks(args):
    """Implementation of 'show-dhcp-networks' action."""
    neutron = get_neutron()
    agent_list = get_network_agents_on_host(socket.gethostname(), neutron,
                                            "DHCP agent")
    list_func = neutron.list_networks_on_dhcp_agent
    dhcp_network_list = get_resource_list_on_agents(agent_list,
                                                    list_func,
                                                    "networks")

    clean_data = clean_resource_list(dhcp_network_list,
                                     allowed_keys=["id", "status", "name"])

    function_set({"dhcp-networks": format_status_output(clean_data)})


def get_lbaasv2_lb(args):
    """Implementation of 'show-loadbalancers' action."""
    neutron = get_neutron()
    agent_list = get_network_agents_on_host(socket.gethostname(),
                                            neutron,
                                            "Loadbalancerv2 agent")
    list_func = neutron.list_loadbalancers_on_lbaas_agent
    lb_list = get_resource_list_on_agents(agent_list,
                                          list_func,
                                          "loadbalancers")

    clean_data = clean_resource_list(lb_list, allowed_keys=["id",
                                                            "status",
                                                            "name"])

    function_set({"load-balancers": format_status_output(clean_data)})


# A dictionary of all the defined actions to callables (which take
# parsed arguments).
ACTIONS = {"pause": pause,
           "resume": resume,
           "restart-services": restart,
           "show-deferred-events": show_deferred_events,
           "run-deferred-hooks": run_deferred_hooks,
           "show-routers": get_routers,
           "show-dhcp-networks": get_dhcp_networks,
           "show-loadbalancers": get_lbaasv2_lb,
           }


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
