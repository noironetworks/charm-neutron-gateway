# vim: set ts=4:et
import os
import uuid
from charmhelpers.core.hookenv import (
    config,
    relation_get,
    relation_ids,
    related_units,
    unit_get,
    network_get_primary_address,
    log,
)
from charmhelpers.contrib.openstack.context import (
    OSContextGenerator,
    NeutronAPIContext,
    NovaVendorMetadataContext,
    NovaVendorMetadataJSONContext,
)
from charmhelpers.contrib.openstack.utils import (
    os_release,
    CompareOpenStackReleases,
)
from charmhelpers.contrib.hahelpers.cluster import (
    eligible_leader
)

from charmhelpers.contrib.network.ip import (
    get_address_in_network,
    get_host_ip,
)

NEUTRON_ML2_PLUGIN = "ml2"
NEUTRON_N1KV_PLUGIN = \
    "neutron.plugins.cisco.n1kv.n1kv_neutron_plugin.N1kvNeutronPluginV2"
NEUTRON_NSX_PLUGIN = "vmware"
NEUTRON_OVS_ODL_PLUGIN = "ml2"

OVS = 'ovs'
N1KV = 'n1kv'
NSX = 'nsx'
OVS_ODL = 'ovs-odl'

NEUTRON = 'neutron'

CORE_PLUGIN = {
    OVS: NEUTRON_ML2_PLUGIN,
    N1KV: NEUTRON_N1KV_PLUGIN,
    NSX: NEUTRON_NSX_PLUGIN,
    OVS_ODL: NEUTRON_OVS_ODL_PLUGIN,
}

NFG_LOG_RATE_LIMIT_MIN = 100
NFG_LOG_BURST_LIMIT_MIN = 25


def get_availability_zone():
    use_juju_az = config('customize-failure-domain')
    juju_az = os.environ.get('JUJU_AVAILABILITY_ZONE')
    return (juju_az if use_juju_az and juju_az
            else config('default-availability-zone'))


def core_plugin():
    return CORE_PLUGIN[config('plugin')]


def get_local_ip():
    fallback = get_host_ip(unit_get('private-address'))
    if config('os-data-network'):
        # NOTE: prefer any existing use of config based networking
        local_ip = get_address_in_network(
            config('os-data-network'),
            fallback)
    else:
        # NOTE: test out network-spaces support, then fallback
        try:
            local_ip = get_host_ip(network_get_primary_address('data'))
        except NotImplementedError:
            local_ip = fallback
    return local_ip


class L3AgentContext(OSContextGenerator):

    def __call__(self):
        api_settings = NeutronAPIContext()()
        ctxt = {}
        if config('run-internal-router') == 'leader':
            ctxt['handle_internal_only_router'] = eligible_leader(None)

        if config('run-internal-router') == 'all':
            ctxt['handle_internal_only_router'] = True

        if config('run-internal-router') == 'none':
            ctxt['handle_internal_only_router'] = False

        if config('external-network-id'):
            ctxt['ext_net_id'] = config('external-network-id')

        if not config('ext-port') and not config('external-network-id'):
            ctxt['external_configuration_new'] = True

        if config('plugin'):
            ctxt['plugin'] = config('plugin')
        if api_settings['enable_dvr']:
            ctxt['agent_mode'] = 'dvr_snat'
        else:
            ctxt['agent_mode'] = 'legacy'
        ctxt['rpc_response_timeout'] = api_settings['rpc_response_timeout']
        ctxt['report_interval'] = api_settings['report_interval']
        ctxt['use_l3ha'] = api_settings['enable_l3ha']

        l3_extension_plugins = api_settings.get('l3_extension_plugins', [])
        ctxt['l3_extension_plugins'] = ','.join(l3_extension_plugins)

        return ctxt


def validate_nfg_log_path(desired_nfg_log_path):
    if not desired_nfg_log_path:
        # None means "we need to use syslog" - no need
        # to check anything on filesystem
        return None

    dst_dir, _ = os.path.split(desired_nfg_log_path)
    path_exists = os.path.exists(dst_dir)
    if not path_exists:
        log(
            "Desired NFG log directory {} not exists! "
            "falling back to syslog".format(dst_dir),
            "WARN"
        )
        return None

    if path_exists and os.path.isdir(desired_nfg_log_path):
        log(
            "Desired NFG log path {} should be file, not directory! "
            "falling back to syslog".format(desired_nfg_log_path),
            "WARN"
        )
        return None

    return desired_nfg_log_path


class NeutronGatewayContext(NeutronAPIContext):

    def __call__(self):
        api_settings = super(NeutronGatewayContext, self).__call__()
        ctxt = {
            'shared_secret': get_shared_secret(),
            'core_plugin': core_plugin(),
            'plugin': config('plugin'),
            'debug': config('debug'),
            'verbose': config('verbose'),
            'l2_population': api_settings['l2_population'],
            'enable_dvr': api_settings['enable_dvr'],
            'enable_l3ha': api_settings['enable_l3ha'],
            'extension_drivers': api_settings['extension_drivers'],
            'overlay_network_type':
            api_settings['overlay_network_type'],
            'rpc_response_timeout': api_settings['rpc_response_timeout'],
            'report_interval': api_settings['report_interval'],
            'availability_zone': get_availability_zone(),
            'enable_nfg_logging': api_settings['enable_nfg_logging'],
            'ovsdb_timeout': config('ovsdb-timeout'),
            'keepalived_healthcheck_interval':
            config('keepalived-healthcheck-interval')
        }

        ctxt['local_ip'] = get_local_ip()
        mappings = config('bridge-mappings')
        if mappings:
            ctxt['bridge_mappings'] = ','.join(mappings.split())

        flat_providers = config('flat-network-providers')
        if flat_providers:
            ctxt['network_providers'] = ','.join(flat_providers.split())

        vlan_ranges = config('vlan-ranges')
        if vlan_ranges:
            ctxt['vlan_ranges'] = ','.join(vlan_ranges.split())

        net_dev_mtu = api_settings['network_device_mtu']
        if net_dev_mtu:
            ctxt['network_device_mtu'] = net_dev_mtu
            ctxt['veth_mtu'] = net_dev_mtu

        ctxt['nfg_log_output_base'] = validate_nfg_log_path(
            config('firewall-group-log-output-base')
        )
        ctxt['nfg_log_rate_limit'] = config(
            'firewall-group-log-rate-limit'
        )
        if ctxt['nfg_log_rate_limit'] is not None:
            ctxt['nfg_log_rate_limit'] = max(
                ctxt['nfg_log_rate_limit'],
                NFG_LOG_RATE_LIMIT_MIN
            )
        ctxt['nfg_log_burst_limit'] = config(
            'firewall-group-log-burst-limit'
        )
        if ctxt['nfg_log_burst_limit'] is not None:
            ctxt['nfg_log_burst_limit'] = max(
                ctxt['nfg_log_burst_limit'],
                NFG_LOG_BURST_LIMIT_MIN
            )

        return ctxt


class NovaMetadataContext(NovaVendorMetadataContext):

    def __init__(self, rel_name='quantum-network-service'):
        super(NovaMetadataContext, self).__init__('neutron-common', [rel_name])
        self.rel_name = rel_name

    def __call__(self):
        ctxt = {}
        cmp_os_release = CompareOpenStackReleases(os_release('neutron-common'))
        if cmp_os_release < 'rocky':
            # if release is Rocky or later, we don't set vendor metadata here
            ctxt.update(super(NovaMetadataContext, self).__call__())
        for rid in relation_ids(self.rel_name):
            for unit in related_units(rid):
                rdata = relation_get(rid=rid, unit=unit)
                secret = rdata.get('shared-metadata-secret')
                if secret:
                    ctxt['shared_secret'] = secret
                    ctxt['nova_metadata_host'] = rdata['nova-metadata-host']
                    ctxt['nova_metadata_port'] = rdata['nova-metadata-port']
                    ctxt['nova_metadata_protocol'] = rdata[
                        'nova-metadata-protocol']
        if not ctxt.get('shared_secret'):
            ctxt['shared_secret'] = get_shared_secret()
            ctxt['nova_metadata_host'] = get_local_ip()
            ctxt['nova_metadata_port'] = '8775'
            ctxt['nova_metadata_protocol'] = 'http'
        return ctxt


class NovaMetadataJSONContext(NovaVendorMetadataJSONContext):

    def __call__(self):
        vdata_values = super(NovaMetadataJSONContext, self).__call__()

        cmp_os_release = CompareOpenStackReleases(os_release('neutron-common'))

        if cmp_os_release < 'rocky':
            return vdata_values
        else:
            # if release is Rocky or later, we don't set vendor metadata here
            return {'vendor_data_json': '{}'}


SHARED_SECRET = "/etc/{}/secret.txt"


def get_shared_secret():
    secret = None
    _path = SHARED_SECRET.format(NEUTRON)
    if not os.path.exists(_path):
        secret = str(uuid.uuid4())
        with open(_path, 'w') as secret_file:
            secret_file.write(secret)
    else:
        with open(_path, 'r') as secret_file:
            secret = secret_file.read().strip()
    return secret
