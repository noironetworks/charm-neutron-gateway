import io

from contextlib import contextmanager

from unittest.mock import (
    MagicMock,
    patch
)
import neutron_contexts

from test_utils import (
    CharmTestCase
)

TO_PATCH = [
    'config',
    'eligible_leader',
    'unit_get',
    'network_get_primary_address',
    'os_release',
    'charmhelpers.contrib.network.ip.log',
]


@contextmanager
def patch_open():
    '''Patch open() to allow mocking both open() itself and the file that is
    yielded.

    Yields the mock for "open" and "file", respectively.'''
    mock_open = MagicMock(spec=open)
    mock_file = MagicMock(spec=io.FileIO)

    @contextmanager
    def stub_open(*args, **kwargs):
        mock_open(*args, **kwargs)
        yield mock_file

    with patch('builtins.open', stub_open):
        yield mock_open, mock_file


class DummyNeutronAPIContext():

    def __init__(self, return_value):
        self.return_value = return_value

    def __call__(self):
        return self.return_value


class TestL3AgentContext(CharmTestCase):

    def setUp(self):
        super(TestL3AgentContext, self).setUp(neutron_contexts,
                                              TO_PATCH)
        self.network_get_primary_address.side_effect = NotImplementedError
        self.config.side_effect = self.test_config.get

    @patch('neutron_contexts.NeutronAPIContext')
    def test_new_ext_network(self, _NeutronAPIContext):
        self.os_release.return_value = 'stein'
        _NeutronAPIContext.return_value = \
            DummyNeutronAPIContext(return_value={
                'enable_dvr': False,
                'report_interval': 30,
                'rpc_response_timeout': 60,
                'enable_l3ha': True,
                'enable_fwaas': True,
                'l3_extension_plugins': ['fwaas_v2'],
            })
        self.test_config.set('run-internal-router', 'none')
        self.test_config.set('external-network-id', '')
        self.eligible_leader.return_value = False
        self.assertEqual(neutron_contexts.L3AgentContext()(),
                         {'agent_mode': 'legacy',
                          'report_interval': 30,
                          'rpc_response_timeout': 60,
                          'use_l3ha': True,
                          'external_configuration_new': True,
                          'handle_internal_only_router': False,
                          'plugin': 'ovs',
                          'l3_extension_plugins': 'fwaas_v2',
                          })

    @patch('neutron_contexts.NeutronAPIContext')
    def test_old_ext_network(self, _NeutronAPIContext):
        self.os_release.return_value = 'rocky'
        _NeutronAPIContext.return_value = \
            DummyNeutronAPIContext(return_value={'enable_dvr': False,
                                                 'report_interval': 30,
                                                 'rpc_response_timeout': 60,
                                                 'enable_l3ha': True,
                                                 })
        self.test_config.set('run-internal-router', 'none')
        self.test_config.set('ext-port', 'eth1')
        self.eligible_leader.return_value = False
        self.assertEqual(neutron_contexts.L3AgentContext()(),
                         {'agent_mode': 'legacy',
                          'report_interval': 30,
                          'rpc_response_timeout': 60,
                          'use_l3ha': True,
                          'handle_internal_only_router': False,
                          'plugin': 'ovs',
                          'l3_extension_plugins': '',
                          })

    @patch('neutron_contexts.NeutronAPIContext')
    def test_hior_leader(self, _NeutronAPIContext):
        self.os_release.return_value = 'rocky'
        _NeutronAPIContext.return_value = \
            DummyNeutronAPIContext(return_value={'enable_dvr': False,
                                                 'report_interval': 30,
                                                 'rpc_response_timeout': 60,
                                                 'enable_l3ha': True,
                                                 'l3_extension_plugins': '',
                                                 })
        self.test_config.set('run-internal-router', 'leader')
        self.test_config.set('external-network-id', 'netid')
        self.eligible_leader.return_value = True
        self.assertEqual(neutron_contexts.L3AgentContext()(),
                         {'agent_mode': 'legacy',
                          'report_interval': 30,
                          'rpc_response_timeout': 60,
                          'use_l3ha': True,
                          'handle_internal_only_router': True,
                          'ext_net_id': 'netid',
                          'plugin': 'ovs',
                          'l3_extension_plugins': '',
                          })

    @patch('neutron_contexts.NeutronAPIContext')
    def test_hior_all(self, _NeutronAPIContext):
        self.os_release.return_value = 'rocky'
        _NeutronAPIContext.return_value = \
            DummyNeutronAPIContext(return_value={'enable_dvr': False,
                                                 'report_interval': 30,
                                                 'rpc_response_timeout': 60,
                                                 'enable_l3ha': True,
                                                 })
        self.test_config.set('run-internal-router', 'all')
        self.test_config.set('external-network-id', 'netid')
        self.eligible_leader.return_value = True
        self.assertEqual(neutron_contexts.L3AgentContext()(),
                         {'agent_mode': 'legacy',
                          'report_interval': 30,
                          'rpc_response_timeout': 60,
                          'use_l3ha': True,
                          'handle_internal_only_router': True,
                          'ext_net_id': 'netid',
                          'plugin': 'ovs',
                          'l3_extension_plugins': '',
                          })

    @patch('neutron_contexts.NeutronAPIContext')
    def test_dvr(self, _NeutronAPIContext):
        self.os_release.return_value = 'rocky'
        _NeutronAPIContext.return_value = \
            DummyNeutronAPIContext(return_value={'enable_dvr': True,
                                                 'report_interval': 30,
                                                 'rpc_response_timeout': 60,
                                                 'enable_l3ha': True,
                                                 })
        self.assertEqual(neutron_contexts.L3AgentContext()()['agent_mode'],
                         'dvr_snat')


class TestNeutronGatewayContext(CharmTestCase):

    def setUp(self):
        super(TestNeutronGatewayContext, self).setUp(neutron_contexts,
                                                     TO_PATCH)
        self.config.side_effect = self.test_config.get
        self.maxDiff = None

    @patch.object(neutron_contexts, 'validate_nfg_log_path', lambda x: x)
    @patch('charmhelpers.contrib.openstack.context.relation_get')
    @patch('charmhelpers.contrib.openstack.context.related_units')
    @patch('charmhelpers.contrib.openstack.context.relation_ids')
    @patch.object(neutron_contexts, 'get_shared_secret')
    def test_all(self, _secret, _rids, _runits, _rget):
        rdata = {'l2-population': 'True',
                 'enable-dvr': 'True',
                 'overlay-network-type': 'gre',
                 'enable-l3ha': 'True',
                 'enable-qos': 'True',
                 'network-device-mtu': 9000,
                 'dns-domain': 'openstack.example.',
                 'enable-nfg-logging': 'True'}
        self.test_config.set('plugin', 'ovs')
        self.test_config.set('debug', False)
        self.test_config.set('verbose', True)
        self.test_config.set('instance-mtu', 1420)
        self.test_config.set('dnsmasq-flags', 'dhcp-userclass=set:ipxe,iPXE,'
                                              'dhcp-match=set:ipxe,175')
        self.test_config.set('dns-servers', '8.8.8.8,4.4.4.4')
        self.test_config.set('vlan-ranges',
                             'physnet1:1000:2000 physnet2:2001:3000')
        self.test_config.set('flat-network-providers', 'physnet3 physnet4')
        self.test_config.set('firewall-group-log-output-base',
                             '/var/log/firewall-logs')
        self.test_config.set('firewall-group-log-rate-limit', 100)
        self.test_config.set('firewall-group-log-burst-limit', 50)

        self.test_config.set('customize-failure-domain', False)
        self.test_config.set('default-availability-zone', 'nova')

        self.test_config.set('ovsdb-timeout', 10)

        self.test_config.set('keepalived-healthcheck-interval', 0)

        self.network_get_primary_address.side_effect = NotImplementedError
        self.unit_get.return_value = '10.5.0.1'
        # Provided by neutron-api relation
        _rids.return_value = ['neutron-plugin-api:0']
        _runits.return_value = ['neutron-api/0']
        _rget.side_effect = lambda *args, **kwargs: rdata
        _secret.return_value = 'testsecret'
        ctxt = neutron_contexts.NeutronGatewayContext()()
        self.assertEqual(ctxt, {
            'shared_secret': 'testsecret',
            'enable_dvr': True,
            'enable_l3ha': True,
            'extension_drivers': 'qos',
            'local_ip': '10.5.0.1',
            'core_plugin': "ml2",
            'plugin': 'ovs',
            'debug': False,
            'verbose': True,
            'l2_population': True,
            'overlay_network_type': 'gre',
            'report_interval': 30,
            'rpc_response_timeout': 60,
            'bridge_mappings': 'physnet1:br-data',
            'network_providers': 'physnet3,physnet4',
            'vlan_ranges': 'physnet1:1000:2000,physnet2:2001:3000',
            'network_device_mtu': 9000,
            'veth_mtu': 9000,
            'availability_zone': 'nova',
            'enable_nfg_logging': True,
            'nfg_log_burst_limit': 50,
            'nfg_log_output_base': '/var/log/firewall-logs',
            'nfg_log_rate_limit': 100,
            'ovsdb_timeout': 10,
            'keepalived_healthcheck_interval': 0,
        })

    @patch.object(neutron_contexts, 'validate_nfg_log_path', lambda x: x)
    @patch('charmhelpers.contrib.openstack.context.relation_get')
    @patch('charmhelpers.contrib.openstack.context.related_units')
    @patch('charmhelpers.contrib.openstack.context.relation_ids')
    @patch.object(neutron_contexts, 'get_shared_secret')
    def test_all_network_spaces(self, _secret, _rids, _runits, _rget):
        rdata = {'l2-population': 'True',
                 'enable-dvr': 'True',
                 'overlay-network-type': 'gre',
                 'enable-l3ha': 'True',
                 'enable-qos': 'True',
                 'network-device-mtu': 9000,
                 'dns-domain': 'openstack.example.'}
        self.test_config.set('plugin', 'ovs')
        self.test_config.set('debug', False)
        self.test_config.set('verbose', True)
        self.test_config.set('instance-mtu', 1420)
        self.test_config.set('dnsmasq-flags', 'dhcp-userclass=set:ipxe,iPXE,'
                                              'dhcp-match=set:ipxe,175')
        self.test_config.set('vlan-ranges',
                             'physnet1:1000:2000 physnet2:2001:3000')
        self.test_config.set('flat-network-providers', 'physnet3 physnet4')

        self.test_config.set('customize-failure-domain', False)
        self.test_config.set('default-availability-zone', 'nova')
        self.test_config.set('ovsdb-timeout', 60)

        self.network_get_primary_address.return_value = '192.168.20.2'
        self.unit_get.return_value = '10.5.0.1'
        # Provided by neutron-api relation
        _rids.return_value = ['neutron-plugin-api:0']
        _runits.return_value = ['neutron-api/0']
        _rget.side_effect = lambda *args, **kwargs: rdata
        _secret.return_value = 'testsecret'
        ctxt = neutron_contexts.NeutronGatewayContext()()
        self.assertEqual(ctxt, {
            'shared_secret': 'testsecret',
            'enable_dvr': True,
            'enable_l3ha': True,
            'extension_drivers': 'qos',
            'local_ip': '192.168.20.2',
            'core_plugin': "ml2",
            'plugin': 'ovs',
            'debug': False,
            'verbose': True,
            'l2_population': True,
            'overlay_network_type': 'gre',
            'report_interval': 30,
            'rpc_response_timeout': 60,
            'bridge_mappings': 'physnet1:br-data',
            'network_providers': 'physnet3,physnet4',
            'vlan_ranges': 'physnet1:1000:2000,physnet2:2001:3000',
            'network_device_mtu': 9000,
            'veth_mtu': 9000,
            'availability_zone': 'nova',
            'enable_nfg_logging': False,
            'nfg_log_burst_limit': 25,
            'nfg_log_output_base': None,
            'nfg_log_rate_limit': None,
            'ovsdb_timeout': 60,
            'keepalived_healthcheck_interval': 30,
        })

    @patch('os.environ.get')
    @patch('charmhelpers.contrib.openstack.context.relation_get')
    @patch('charmhelpers.contrib.openstack.context.related_units')
    @patch('charmhelpers.contrib.openstack.context.relation_ids')
    @patch.object(neutron_contexts, 'get_shared_secret')
    def test_availability_zone_no_juju_with_env(self, _secret, _rids,
                                                _runits, _rget,
                                                mock_get):
        self.os_release.return_value = 'icehouse'

        def environ_get_side_effect(key):
            return {
                'JUJU_AVAILABILITY_ZONE': 'az1',
                'PATH': 'foobar',
            }[key]
        mock_get.side_effect = environ_get_side_effect

        self.test_config.set('customize-failure-domain', False)
        self.test_config.set('default-availability-zone', 'nova')

        context = neutron_contexts.NeutronGatewayContext()
        self.assertEqual(
            'nova', context()['availability_zone'])

    @patch('neutron_utils.config')
    @patch('os.environ.get')
    @patch('charmhelpers.contrib.openstack.context.relation_get')
    @patch('charmhelpers.contrib.openstack.context.related_units')
    @patch('charmhelpers.contrib.openstack.context.relation_ids')
    @patch.object(neutron_contexts, 'get_shared_secret')
    def test_availability_zone_no_juju_no_env(self, _secret, _rids,
                                              _runits, _rget,
                                              mock_get, mock_config):
        self.os_release.return_value = 'icehouse'

        def environ_get_side_effect(key):
            return {
                'JUJU_AVAILABILITY_ZONE': '',
                'PATH': 'foobar',
            }[key]
        mock_get.side_effect = environ_get_side_effect

        def config_side_effect(key):
            return {
                'customize-failure-domain': False,
                'default-availability-zone': 'nova',
            }[key]

        mock_config.side_effect = config_side_effect
        context = neutron_contexts.NeutronGatewayContext()

        self.assertEqual(
            'nova', context()['availability_zone'])

    @patch('neutron_utils.config')
    @patch('os.environ.get')
    @patch('charmhelpers.contrib.openstack.context.relation_get')
    @patch('charmhelpers.contrib.openstack.context.related_units')
    @patch('charmhelpers.contrib.openstack.context.relation_ids')
    @patch.object(neutron_contexts, 'get_shared_secret')
    def test_availability_zone_juju(self, _secret, _rids,
                                    _runits, _rget,
                                    mock_get, mock_config):
        self.os_release.return_value = 'icehouse'

        def environ_get_side_effect(key):
            return {
                'JUJU_AVAILABILITY_ZONE': 'az1',
                'PATH': 'foobar',
            }[key]
        mock_get.side_effect = environ_get_side_effect

        mock_config.side_effect = self.test_config.get
        self.test_config.set('customize-failure-domain', True)
        context = neutron_contexts.NeutronGatewayContext()
        self.assertEqual(
            'az1', context()['availability_zone'])

    @patch('charmhelpers.contrib.openstack.context.relation_get')
    @patch('charmhelpers.contrib.openstack.context.related_units')
    @patch('charmhelpers.contrib.openstack.context.relation_ids')
    @patch.object(neutron_contexts, 'get_shared_secret')
    def test_nfg_min_settings(self, _secret, _rids, _runits, _rget):
        self.os_release.return_value = 'icehouse'
        self.test_config.set('firewall-group-log-rate-limit', 90)
        self.test_config.set('firewall-group-log-burst-limit', 20)
        self.network_get_primary_address.return_value = '192.168.20.2'
        self.unit_get.return_value = '10.5.0.1'
        ctxt = neutron_contexts.NeutronGatewayContext()()
        self.assertEqual(ctxt['nfg_log_burst_limit'], 25)
        self.assertEqual(ctxt['nfg_log_rate_limit'], 100)


class TestSharedSecret(CharmTestCase):

    def setUp(self):
        super(TestSharedSecret, self).setUp(neutron_contexts,
                                            TO_PATCH)
        self.config.side_effect = self.test_config.get
        self.network_get_primary_address.side_effect = NotImplementedError

    @patch('os.path')
    @patch('uuid.uuid4')
    def test_secret_created_stored(self, _uuid4, _path):
        _path.exists.return_value = False
        _uuid4.return_value = 'secret_thing'
        with patch_open() as (_open, _file):
            self.assertEqual(neutron_contexts.get_shared_secret(),
                             'secret_thing')
            _open.assert_called_with(
                neutron_contexts.SHARED_SECRET.format('neutron'), 'w')
            _file.write.assert_called_with('secret_thing')

    @patch('os.path')
    def test_secret_retrieved(self, _path):
        _path.exists.return_value = True
        with patch_open() as (_open, _file):
            _file.read.return_value = 'secret_thing\n'
            self.assertEqual(neutron_contexts.get_shared_secret(),
                             'secret_thing')
            _open.assert_called_with(
                neutron_contexts.SHARED_SECRET.format('neutron'), 'r')


class TestMisc(CharmTestCase):

    def setUp(self):
        super(TestMisc,
              self).setUp(neutron_contexts,
                          TO_PATCH)

    def test_core_plugin_ml2(self):
        self.config.return_value = 'ovs'
        self.assertEqual(neutron_contexts.core_plugin(),
                         neutron_contexts.NEUTRON_ML2_PLUGIN)


class TestNovaMetadataContext(CharmTestCase):

    def setUp(self):
        super(TestNovaMetadataContext, self).setUp(neutron_contexts,
                                                   TO_PATCH)
        self.config.side_effect = self.test_config.get

    @patch.object(neutron_contexts.NovaVendorMetadataContext, '__call__')
    @patch.object(neutron_contexts, 'get_local_ip')
    @patch.object(neutron_contexts, 'get_shared_secret')
    @patch.object(neutron_contexts, 'relation_ids')
    def test_vendordata_queens(self, _relation_ids, _get_shared_secret,
                               _get_local_ip, parent):
        _get_shared_secret.return_value = 'asecret'
        _get_local_ip.return_value = '127.0.0.1'
        _relation_ids.return_value = []
        _vdata_url = 'http://example.org/vdata'
        _vdata_providers = 'StaticJSON,DynamicJSON'
        self.os_release.return_value = 'queens'
        parent.return_value = {
            'vendor_data': True,
            'vendor_data_url': _vdata_url,
            'vendordata_providers': _vdata_providers,
        }

        ctxt = neutron_contexts.NovaMetadataContext()()

        self.assertTrue(ctxt['vendor_data'])
        self.assertEqual(ctxt['vendordata_providers'], _vdata_providers)
        self.assertEqual(ctxt['vendor_data_url'], _vdata_url)

    @patch.object(neutron_contexts.NovaVendorMetadataContext, '__call__')
    @patch.object(neutron_contexts, 'get_local_ip')
    @patch.object(neutron_contexts, 'get_shared_secret')
    @patch.object(neutron_contexts, 'relation_ids')
    def test_vendordata_rocky(self, _relation_ids, _get_shared_secret,
                              _get_local_ip, parent):
        _get_shared_secret.return_value = 'asecret'
        _get_local_ip.return_value = '127.0.0.1'
        _relation_ids.return_value = []
        self.os_release.return_value = 'rocky'
        parent.return_value = {
            'vendor_data': True,
            'vendor_data_url': 'http://example.org/vdata',
            'vendordata_providers': 'StaticJSON,DynamicJSON',
        }

        ctxt = neutron_contexts.NovaMetadataContext()()

        self.assertNotIn('vendor_data', ctxt)
        self.assertNotIn('vendor_data_url', ctxt)
        self.assertNotIn('vendordata_providers', ctxt)

    @patch.object(neutron_contexts.NovaVendorMetadataJSONContext, '__call__')
    def test_vendordata_json_queens(self, parent):
        self.os_release.return_value = 'queens'
        result = {
            'vendor_data_json': '{"good": "json"}',
        }
        parent.return_value = result

        ctxt = neutron_contexts.NovaMetadataJSONContext('neutron-common')()

        self.assertEqual(result, ctxt)

    @patch.object(neutron_contexts.NovaVendorMetadataJSONContext, '__call__')
    def test_vendordata_json_rocky(self, parent):
        self.os_release.return_value = 'rocky'
        result = {
            'vendor_data_json': '{}',
        }
        parent.return_value = {
            'vendor_data_json': '{"good": "json"}',
        }

        ctxt = neutron_contexts.NovaMetadataJSONContext('neutron-common')()

        self.assertEqual(result, ctxt)

    @patch.object(neutron_contexts, 'relation_get')
    @patch.object(neutron_contexts, 'related_units')
    @patch.object(neutron_contexts, 'relation_ids')
    def test_NovaMetadataContext_with_relations(self, _relation_ids,
                                                _related_units, _relation_get):
        _relation_ids.return_value = ['rid:1']
        _related_units.return_value = ['nova-cloud-contoller/0']
        _relation_get.return_value = {
            'nova-metadata-host': '10.0.0.10',
            'nova-metadata-port': '8775',
            'nova-metadata-protocol': 'http',
            'shared-metadata-secret': 'auuid'}
        self.os_release.return_value = 'rocky'

        self.assertEqual(
            neutron_contexts.NovaMetadataContext()(),
            {
                'nova_metadata_host': '10.0.0.10',
                'nova_metadata_port': '8775',
                'nova_metadata_protocol': 'http',
                'shared_secret': 'auuid'})

    @patch.object(neutron_contexts, 'get_local_ip')
    @patch.object(neutron_contexts, 'get_shared_secret')
    @patch.object(neutron_contexts, 'relation_ids')
    def test_NovaMetadataContext_no_relations(self, _relation_ids,
                                              _get_shared_secret,
                                              _get_local_ip):
        _relation_ids.return_value = []
        _get_shared_secret.return_value = 'buuid'
        _get_local_ip.return_value = '127.0.0.1'
        self.os_release.return_value = 'rocky'

        self.assertEqual(
            neutron_contexts.NovaMetadataContext()(),
            {
                'nova_metadata_host': '127.0.0.1',
                'nova_metadata_port': '8775',
                'nova_metadata_protocol': 'http',
                'shared_secret': 'buuid'})


class TestGetAvailabilityZone(CharmTestCase):

    def setUp(self):
        super(TestGetAvailabilityZone, self).setUp(neutron_contexts, TO_PATCH)

    @patch.object(neutron_contexts.os.environ, 'get')
    def test_get_az_customize_with_env(self, os_environ_get_mock):
        self.config.side_effect = self.test_config.get
        self.test_config.set('customize-failure-domain', True)
        self.test_config.set('default-availability-zone', 'nova')

        def os_environ_get_side_effect(key):
            return {
                'JUJU_AVAILABILITY_ZONE': 'az1',
            }[key]
        os_environ_get_mock.side_effect = os_environ_get_side_effect
        az = neutron_contexts.get_availability_zone()
        self.assertEqual('az1', az)

    @patch.object(neutron_contexts.os.environ, 'get')
    def test_get_az_customize_without_env(self, os_environ_get_mock):
        self.config.side_effect = self.test_config.get
        self.test_config.set('customize-failure-domain', True)
        self.test_config.set('default-availability-zone', 'mynova')

        def os_environ_get_side_effect(key):
            return {
                'JUJU_AVAILABILITY_ZONE': '',
            }[key]
        os_environ_get_mock.side_effect = os_environ_get_side_effect
        az = neutron_contexts.get_availability_zone()
        self.assertEqual('mynova', az)

    @patch.object(neutron_contexts.os.environ, 'get')
    def test_get_az_no_customize_without_env(self, os_environ_get_mock):
        self.config.side_effect = self.test_config.get
        self.test_config.set('customize-failure-domain', False)
        self.test_config.set('default-availability-zone', 'nova')

        def os_environ_get_side_effect(key):
            return {
                'JUJU_AVAILABILITY_ZONE': '',
            }[key]
        os_environ_get_mock.side_effect = os_environ_get_side_effect
        az = neutron_contexts.get_availability_zone()
        self.assertEqual('nova', az)

    @patch.object(neutron_contexts.os.environ, 'get')
    def test_get_az_no_customize_with_env(self, os_environ_get_mock):
        self.config.side_effect = self.test_config.get
        self.test_config.set('customize-failure-domain', False)
        self.test_config.set('default-availability-zone', 'nova')

        def os_environ_get_side_effect(key):
            return {
                'JUJU_AVAILABILITY_ZONE': 'az1',
            }[key]
        os_environ_get_mock.side_effect = os_environ_get_side_effect
        az = neutron_contexts.get_availability_zone()
        self.assertEqual('nova', az)
