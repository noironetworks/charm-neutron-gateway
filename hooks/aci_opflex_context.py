#!/usr/bin/env python

from charmhelpers.core.hookenv import config
from charmhelpers.contrib.openstack import context, templating
from charmhelpers.contrib.openstack.utils import get_host_ip
from charmhelpers.core.hookenv import (
    config,
    relation_get,
    relation_ids,
    related_units,
    unit_get,
    unit_private_ip,
    network_get_primary_address,
)
from socket import gethostname

class AciOpflexConfigContext(context.OSContextGenerator):
    def __call__(self):
        ctxt = {}

        ctxt['debug_level'] = config('aci-opflex-debug-level')
        ctxt['ovs_bridge'] = 'br-int'
        ctxt['apic_system_id'] = config('aci-apic-system-id')
        ctxt['hostname'] = gethostname()
        ctxt['opflex_peer_ip'] = config('aci-opflex-peer-ip')
        ctxt['aci_encap'] = config('aci-encap')
        ctxt['opflex_uplink_iface'] = config('aci-uplink-interface')
        ctxt['aci_infra_vlan'] = config('aci-infra-vlan')
        ctxt['opflex_remote_ip'] = config('aci-opflex-remote-ip')
        if config('aci-encap') == "vxlan":
            ctxt['opflex_encap_iface'] = 'br-fab_vxlan0'
        else:
            ctxt['opflex_encap_iface'] = ''

        return ctxt

class RemoteRestartContext(context.OSContextGenerator):

    def __init__(self, interfaces=None):
        self.interfaces = interfaces or ['neutron-plugin']

    def __call__(self):
        rids = []
        for interface in self.interfaces:
            rids.extend(relation_ids(interface))
        ctxt = {}
        for rid in rids:
            for unit in related_units(rid):
                remote_data = relation_get(
                    rid=rid,
                    unit=unit)
                for k, v in remote_data.items():
                    if k.startswith('restart-trigger'):
                        restart_key = k.replace('-', '_')
                        try:
                            ctxt[restart_key].append(v)
                        except KeyError:
                            ctxt[restart_key] = [v]
        for restart_key in ctxt.keys():
            ctxt[restart_key] = '-'.join(sorted(ctxt[restart_key]))
        return ctxt

class OVSPluginContext(context.OSContextGenerator):
    def __call__(self):
        ctxt = {}

        ctxt['local_ip'] = get_host_ip(unit_get('private-address'))

        return ctxt
