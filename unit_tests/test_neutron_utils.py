from mock import MagicMock, call, patch, ANY

import charmhelpers.core.hookenv as hookenv
import neutron_utils
try:
    import neutronclient
except ImportError:
    neutronclient = None

from test_utils import (
    CharmTestCase
)

TO_PATCH = [
    'config',
    'get_os_codename_install_source',
    'apt_update',
    'apt_upgrade',
    'apt_install',
    'configure_installation_source',
    'log',
    'add_bridge',
    'add_bridge_port',
    'add_ovsbridge_linuxbridge',
    'is_linuxbridge_interface',
    'headers_package',
    'full_restart',
    'os_release',
    'service_running',
    'NetworkServiceContext',
    'ExternalPortContext',
    'service_stop',
    'determine_dkms_package',
    'service_restart',
    'is_relation_made',
    'lsb_release',
    'mkdir',
    'copy2',
    'init_is_systemd',
    'os_application_version_set',
    'NeutronAPIContext',
    'enable_ipfix',
    'disable_ipfix',
]


class TestNeutronUtils(CharmTestCase):

    def setUp(self):
        super(TestNeutronUtils, self).setUp(neutron_utils, TO_PATCH)
        self.headers_package.return_value = 'linux-headers-2.6.18'
        self._set_distrib_codename('trusty')
        self.maxDiff = None

    def tearDown(self):
        # Reset cached cache
        hookenv.cache = {}

    def _set_distrib_codename(self, newcodename):
        self.lsb_release.return_value = {'DISTRIB_CODENAME': newcodename}

    def test_valid_plugin(self):
        self.config.return_value = 'ovs'
        self.assertTrue(neutron_utils.valid_plugin())
        self.config.return_value = 'nsx'
        self.assertTrue(neutron_utils.valid_plugin())

    def test_invalid_plugin(self):
        self.config.return_value = 'invalid'
        self.assertFalse(neutron_utils.valid_plugin())

    def test_get_early_packages_ovs(self):
        self.config.return_value = 'ovs'
        self.determine_dkms_package.return_value = [
            'openvswitch-datapath-dkms']
        self.assertEqual(
            neutron_utils.get_early_packages(),
            ['openvswitch-datapath-dkms', 'linux-headers-2.6.18'])

    def test_get_early_packages_nsx(self):
        self.config.return_value = 'nsx'
        self.assertEqual(
            neutron_utils.get_early_packages(),
            [])

    def test_get_early_packages_empty(self):
        self.config.return_value = 'noop'
        self.assertEqual(neutron_utils.get_early_packages(),
                         [])

    def test_get_packages_ovs_icehouse(self):
        self.config.return_value = 'ovs'
        self.os_release.return_value = 'icehouse'
        self.assertTrue('neutron-vpn-agent' in neutron_utils.get_packages())
        self.assertFalse('neutron-l3-agent' in neutron_utils.get_packages())

    def test_get_packages_ovs_juno_utopic(self):
        self.config.return_value = 'ovs'
        self.os_release.return_value = 'juno'
        self._set_distrib_codename('utopic')
        self.assertFalse('neutron-vpn-agent' in neutron_utils.get_packages())
        self.assertTrue('neutron-l3-agent' in neutron_utils.get_packages())

    def test_get_packages_ovs_juno_trusty(self):
        self.config.return_value = 'ovs'
        self.os_release.return_value = 'juno'
        self.assertTrue('neutron-vpn-agent' in neutron_utils.get_packages())
        self.assertFalse('neutron-l3-agent' in neutron_utils.get_packages())

    def test_get_packages_ovs_kilo(self):
        self.config.return_value = 'ovs'
        self.os_release.return_value = 'kilo'
        self.assertTrue('python-neutron-fwaas' in neutron_utils.get_packages())

    def test_get_packages_ovs_liberty(self):
        self.config.return_value = 'ovs'
        self.os_release.return_value = 'liberty'
        packages = neutron_utils.get_packages()
        self.assertTrue('neutron-metering-agent' in packages)
        self.assertFalse('neutron-plugin-metering-agent' in packages)
        self.assertFalse('python-mysqldb' in packages)
        self.assertTrue('python-pymysql' in packages)

    def test_get_packages_ovs_mitaka(self):
        self.config.return_value = 'ovs'
        self.os_release.return_value = 'mitaka'
        packages = neutron_utils.get_packages()
        self.assertTrue('neutron-metering-agent' in packages)
        self.assertFalse('neutron-plugin-metering-agent' in packages)
        self.assertTrue('neutron-openvswitch-agent' in packages)
        self.assertFalse('neutron-plugin-openvswitch-agent' in packages)
        self.assertFalse('python-mysqldb' in packages)
        self.assertTrue('python-pymysql' in packages)

    def test_get_packages_ovs_newton(self):
        self.config.return_value = 'ovs'
        self.os_release.return_value = 'newton'
        packages = neutron_utils.get_packages()
        self.assertTrue('neutron-metering-agent' in packages)
        self.assertFalse('neutron-plugin-metering-agent' in packages)
        self.assertTrue('neutron-openvswitch-agent' in packages)
        self.assertFalse('neutron-plugin-openvswitch-agent' in packages)
        self.assertFalse('neutron-lbaas-agent' in packages)
        self.assertFalse('python-mysqldb' in packages)
        self.assertTrue('python-pymysql' in packages)

    def test_get_packages_ovsodl_icehouse(self):
        self.config.return_value = 'ovs-odl'
        self.os_release.return_value = 'icehouse'
        packages = neutron_utils.get_packages()
        self.assertTrue('neutron-metering-agent' in packages)
        self.assertFalse('neutron-plugin-metering-agent' in packages)
        self.assertFalse('neutron-plugin-openvswitch-agent' in packages)
        self.assertFalse('neutron-openvswitch-agent' in packages)
        self.assertTrue('neutron-lbaas-agent' in packages)

    def test_get_packages_ovsodl_newton(self):
        self.config.return_value = 'ovs-odl'
        self.os_release.return_value = 'newton'
        packages = neutron_utils.get_packages()
        self.assertTrue('neutron-metering-agent' in packages)
        self.assertFalse('neutron-plugin-metering-agent' in packages)
        self.assertFalse('neutron-plugin-openvswitch-agent' in packages)
        self.assertFalse('neutron-openvswitch-agent' in packages)
        self.assertFalse('neutron-lbaas-agent' in packages)
        self.assertTrue('neutron-lbaasv2-agent' in packages)

    def test_get_packages_l3ha(self):
        self.config.return_value = 'ovs'
        self.get_os_codename_install_source.return_value = 'juno'
        self.os_release.return_value = 'juno'
        self.assertTrue('keepalived' in neutron_utils.get_packages())

    @patch('charmhelpers.contrib.openstack.context.config')
    def test_configure_ovs_starts_service_if_required(self, mock_config):
        mock_config.side_effect = self.test_config.get
        self.config.return_value = 'ovs'
        self.service_running.return_value = False
        neutron_utils.configure_ovs()
        self.assertTrue(self.full_restart.called)

    def test_configure_ovs_doesnt_restart_service(self):
        self.service_running.return_value = True
        neutron_utils.configure_ovs()
        self.assertFalse(self.full_restart.called)

    @patch('charmhelpers.contrib.openstack.context.config')
    def test_configure_ovs_ovs_ext_port(self, mock_config):
        mock_config.side_effect = self.test_config.get
        self.config.side_effect = self.test_config.get
        self.test_config.set('plugin', 'ovs')
        self.test_config.set('ext-port', 'eth0')
        self.ExternalPortContext.return_value = \
            DummyExternalPortContext(return_value={'ext_port': 'eth0'})
        neutron_utils.configure_ovs()
        self.add_bridge.assert_has_calls([
            call('br-int'),
            call('br-ex'),
            call('br-data')
        ])
        self.add_bridge_port.assert_called_with('br-ex', 'eth0')

    @patch('charmhelpers.contrib.openstack.context.config')
    def test_configure_ovs_ovs_data_port(self, mock_config):
        self.is_linuxbridge_interface.return_value = False
        mock_config.side_effect = self.test_config.get
        self.config.side_effect = self.test_config.get
        self.test_config.set('plugin', 'ovs')
        self.ExternalPortContext.return_value = \
            DummyExternalPortContext(return_value=None)
        # Test back-compatibility i.e. port but no bridge (so br-data is
        # assumed)
        self.test_config.set('data-port', 'eth0')
        neutron_utils.configure_ovs()
        self.add_bridge.assert_has_calls([
            call('br-int'),
            call('br-ex'),
            call('br-data')
        ])
        calls = [call('br-data', 'eth0', promisc=True)]
        self.add_bridge_port.assert_has_calls(calls)

        # Now test with bridge:port format and bogus bridge
        self.test_config.set('data-port', 'br-foo:eth0')
        self.add_bridge.reset_mock()
        self.add_bridge_port.reset_mock()
        neutron_utils.configure_ovs()
        self.add_bridge.assert_has_calls([
            call('br-int'),
            call('br-ex'),
            call('br-data')
        ])
        # Not called since we have a bogus bridge in data-ports
        self.assertFalse(self.add_bridge_port.called)

        # Now test with bridge:port format
        self.test_config.set('bridge-mappings', 'net1:br1')
        self.test_config.set('data-port', 'br1:eth0.100 br1:eth0.200')
        self.add_bridge.reset_mock()
        self.add_bridge_port.reset_mock()
        neutron_utils.configure_ovs()
        self.add_bridge.assert_has_calls([
            call('br-int'),
            call('br-ex'),
            call('br1')
        ])
        calls = [call('br1', 'eth0.100', promisc=True),
                 call('br1', 'eth0.200', promisc=True)]
        self.add_bridge_port.assert_has_calls(calls, any_order=True)

    @patch('charmhelpers.contrib.openstack.context.config')
    def test_configure_ovs_ovs_data_port_bridge(self, mock_config):
        self.is_linuxbridge_interface.return_value = True
        mock_config.side_effect = self.test_config.get
        self.config.side_effect = self.test_config.get
        self.test_config.set('plugin', 'ovs')
        self.ExternalPortContext.return_value = \
            DummyExternalPortContext(return_value=None)
        # Test back-compatibility i.e. port but no bridge (so br-data is
        # assumed)
        self.test_config.set('data-port', 'br-eth0')
        neutron_utils.configure_ovs()
        self.add_bridge.assert_has_calls([
            call('br-int'),
            call('br-ex'),
            call('br-data')
        ])
        calls = [call('br-data', 'br-eth0')]
        self.add_ovsbridge_linuxbridge.assert_has_calls(calls)

    @patch('charmhelpers.contrib.openstack.context.config')
    def test_configure_ovs_enable_ipfix(self, mock_config):
        mock_config.side_effect = self.test_config.get
        self.config.side_effect = self.test_config.get
        self.test_config.set('plugin', 'ovs')
        self.test_config.set('ipfix-target', '127.0.0.1:80')
        neutron_utils.configure_ovs()
        self.enable_ipfix.assert_has_calls([
            call('br-int', '127.0.0.1:80'),
            call('br-ex', '127.0.0.1:80'),
            call('br-data', '127.0.0.1:80'),
        ])

    @patch.object(neutron_utils, 'register_configs')
    @patch('charmhelpers.contrib.openstack.templating.OSConfigRenderer')
    def test_do_openstack_upgrade(self, mock_renderer,
                                  mock_register_configs):
        mock_configs = MagicMock()
        mock_register_configs.return_value = mock_configs
        self.config.side_effect = self.test_config.get
        self.is_relation_made.return_value = False
        self.test_config.set('openstack-origin', 'cloud:precise-havana')
        self.test_config.set('plugin', 'ovs')
        self.get_os_codename_install_source.return_value = 'havana'
        self.os_release.return_value = 'havana'
        neutron_utils.do_openstack_upgrade(mock_configs)
        mock_register_configs.assert_called_with('havana')
        self.assertTrue(self.log.called)
        self.apt_update.assert_called_with(fatal=True)
        dpkg_opts = [
            '--option', 'Dpkg::Options::=--force-confnew',
            '--option', 'Dpkg::Options::=--force-confdef',
        ]
        self.apt_upgrade.assert_called_with(
            options=dpkg_opts, fatal=True, dist=True
        )
        self.configure_installation_source.assert_called_with(
            'cloud:precise-havana'
        )

    @patch('charmhelpers.contrib.openstack.templating.OSConfigRenderer')
    def test_register_configs_ovs(self, mock_renderer):
        self.config.return_value = 'ovs'
        self.os_release.return_value = 'diablo'
        self.is_relation_made.return_value = False
        configs = neutron_utils.register_configs()
        confs = [neutron_utils.NEUTRON_DHCP_AGENT_CONF,
                 neutron_utils.NEUTRON_METADATA_AGENT_CONF,
                 neutron_utils.NOVA_CONF,
                 neutron_utils.NEUTRON_CONF,
                 neutron_utils.NEUTRON_L3_AGENT_CONF,
                 neutron_utils.NEUTRON_ML2_PLUGIN_CONF,
                 neutron_utils.EXT_PORT_CONF]
        for conf in confs:
            configs.register.assert_any_call(conf, ANY)

    @patch('charmhelpers.contrib.openstack.templating.OSConfigRenderer')
    def test_register_configs_ovs_odl(self, mock_renderer):
        self.config.side_effect = self.test_config.get
        self.test_config.set('plugin', 'ovs-odl')
        self.is_relation_made.return_value = False
        self.get_os_codename_install_source.return_value = 'icehouse'
        self.os_release.return_value = 'icehouse'
        configs = neutron_utils.register_configs()
        confs = [neutron_utils.NEUTRON_DHCP_AGENT_CONF,
                 neutron_utils.NEUTRON_METADATA_AGENT_CONF,
                 neutron_utils.NOVA_CONF,
                 neutron_utils.NEUTRON_CONF,
                 neutron_utils.NEUTRON_L3_AGENT_CONF,
                 neutron_utils.EXT_PORT_CONF]
        for conf in confs:
            configs.register.assert_any_call(conf, ANY)

    @patch('charmhelpers.contrib.openstack.templating.OSConfigRenderer')
    def test_register_configs_amqp_nova(self, mock_renderer):
        self.config.return_value = 'ovs'
        self.is_relation_made.return_value = True
        self.os_release.return_value = 'diablo'
        configs = neutron_utils.register_configs()
        confs = [neutron_utils.NEUTRON_DHCP_AGENT_CONF,
                 neutron_utils.NEUTRON_METADATA_AGENT_CONF,
                 neutron_utils.NOVA_CONF,
                 neutron_utils.NEUTRON_CONF,
                 neutron_utils.NEUTRON_L3_AGENT_CONF,
                 neutron_utils.NEUTRON_ML2_PLUGIN_CONF,
                 neutron_utils.EXT_PORT_CONF]
        for conf in confs:
            configs.register.assert_any_call(conf, ANY)

    @patch.object(neutron_utils, 'get_packages')
    def test_restart_map_ovs(self, mock_get_packages):
        self.config.return_value = 'ovs'
        self.get_os_codename_install_source.return_value = 'havana'
        mock_get_packages.return_value = ['neutron-vpn-agent']
        self.os_release.return_value = 'icehouse'
        ex_map = {
            neutron_utils.NEUTRON_CONF: ['neutron-lbaas-agent',
                                         'neutron-plugin-openvswitch-agent',
                                         'neutron-vpn-agent',
                                         'neutron-dhcp-agent',
                                         'neutron-metering-agent',
                                         'neutron-metadata-agent'],
            neutron_utils.NEUTRON_DNSMASQ_CONF: ['neutron-dhcp-agent'],
            neutron_utils.NEUTRON_LBAAS_AGENT_CONF:
            ['neutron-lbaas-agent'],
            neutron_utils.NEUTRON_ML2_PLUGIN_CONF:
            ['neutron-plugin-openvswitch-agent'],
            neutron_utils.NEUTRON_METADATA_AGENT_CONF:
            ['neutron-metadata-agent'],
            neutron_utils.NEUTRON_VPNAAS_AGENT_CONF: [
                'neutron-vpn-agent'],
            neutron_utils.NEUTRON_L3_AGENT_CONF: ['neutron-vpn-agent'],
            neutron_utils.NEUTRON_DHCP_AGENT_CONF: ['neutron-dhcp-agent'],
            neutron_utils.NEUTRON_FWAAS_CONF: ['neutron-vpn-agent'],
            neutron_utils.NEUTRON_METERING_AGENT_CONF:
            ['neutron-metering-agent'],
            neutron_utils.NOVA_CONF: ['nova-api-metadata'],
            neutron_utils.EXT_PORT_CONF: ['ext-port'],
            neutron_utils.PHY_NIC_MTU_CONF: ['os-charm-phy-nic-mtu'],
            neutron_utils.NEUTRON_DHCP_AA_PROFILE_PATH: ['neutron-dhcp-agent'],
            neutron_utils.NEUTRON_OVS_AA_PROFILE_PATH:
                ['neutron-plugin-openvswitch-agent'],
            neutron_utils.NEUTRON_L3_AA_PROFILE_PATH: ['neutron-vpn-agent'],
            neutron_utils.NEUTRON_LBAAS_AA_PROFILE_PATH:
            ['neutron-lbaas-agent'],
            neutron_utils.NEUTRON_METADATA_AA_PROFILE_PATH:
            ['neutron-metadata-agent'],
            neutron_utils.NEUTRON_METERING_AA_PROFILE_PATH:
            ['neutron-metering-agent'],
            neutron_utils.NOVA_API_METADATA_AA_PROFILE_PATH:
            ['nova-api-metadata'],
        }
        self.assertEqual(neutron_utils.restart_map(), ex_map)

    @patch.object(neutron_utils, 'get_packages')
    def test_restart_map_ovs_mitaka(self, mock_get_packages):
        self.config.return_value = 'ovs'
        mock_get_packages.return_value = ['neutron-vpn-agent']
        self.os_release.return_value = 'mitaka'
        ex_map = {
            neutron_utils.NEUTRON_CONF: ['neutron-lbaas-agent',
                                         'neutron-vpn-agent',
                                         'neutron-dhcp-agent',
                                         'neutron-metering-agent',
                                         'neutron-metadata-agent',
                                         'neutron-openvswitch-agent'],
            neutron_utils.NEUTRON_DNSMASQ_CONF: ['neutron-dhcp-agent'],
            neutron_utils.NEUTRON_LBAAS_AGENT_CONF:
            ['neutron-lbaas-agent'],
            neutron_utils.NEUTRON_OVS_AGENT_CONF:
            ['neutron-openvswitch-agent'],
            neutron_utils.NEUTRON_METADATA_AGENT_CONF:
            ['neutron-metadata-agent'],
            neutron_utils.NEUTRON_VPNAAS_AGENT_CONF: ['neutron-vpn-agent'],
            neutron_utils.NEUTRON_L3_AGENT_CONF: ['neutron-vpn-agent'],
            neutron_utils.NEUTRON_DHCP_AGENT_CONF: ['neutron-dhcp-agent'],
            neutron_utils.NEUTRON_FWAAS_CONF: ['neutron-vpn-agent'],
            neutron_utils.NEUTRON_METERING_AGENT_CONF:
            ['neutron-metering-agent'],
            neutron_utils.NOVA_CONF: ['nova-api-metadata'],
            neutron_utils.EXT_PORT_CONF: ['ext-port'],
            neutron_utils.PHY_NIC_MTU_CONF: ['os-charm-phy-nic-mtu'],
            neutron_utils.NEUTRON_DHCP_AA_PROFILE_PATH: ['neutron-dhcp-agent'],
            neutron_utils.NEUTRON_OVS_AA_PROFILE_PATH:
                ['neutron-openvswitch-agent'],
            neutron_utils.NEUTRON_L3_AA_PROFILE_PATH: ['neutron-vpn-agent'],
            neutron_utils.NEUTRON_LBAAS_AA_PROFILE_PATH:
            ['neutron-lbaas-agent'],
            neutron_utils.NEUTRON_METADATA_AA_PROFILE_PATH:
            ['neutron-metadata-agent'],
            neutron_utils.NEUTRON_METERING_AA_PROFILE_PATH:
            ['neutron-metering-agent'],
            neutron_utils.NOVA_API_METADATA_AA_PROFILE_PATH:
            ['nova-api-metadata'],
        }
        self.assertEqual(neutron_utils.restart_map(), ex_map)

    @patch.object(neutron_utils, 'get_packages')
    def test_restart_map_ovs_newton(self, mock_get_packages):
        self.config.return_value = 'ovs'
        mock_get_packages.return_value = ['neutron-vpn-agent']
        self.os_release.return_value = 'newton'
        ex_map = {
            neutron_utils.NEUTRON_CONF: ['neutron-vpn-agent',
                                         'neutron-lbaasv2-agent',
                                         'neutron-dhcp-agent',
                                         'neutron-metering-agent',
                                         'neutron-metadata-agent',
                                         'neutron-openvswitch-agent'],
            neutron_utils.NEUTRON_DNSMASQ_CONF: ['neutron-dhcp-agent'],
            neutron_utils.NEUTRON_LBAAS_AGENT_CONF:
            ['neutron-lbaasv2-agent'],
            neutron_utils.NEUTRON_OVS_AGENT_CONF:
            ['neutron-openvswitch-agent'],
            neutron_utils.NEUTRON_METADATA_AGENT_CONF:
            ['neutron-metadata-agent'],
            neutron_utils.NEUTRON_VPNAAS_AGENT_CONF: ['neutron-vpn-agent'],
            neutron_utils.NEUTRON_L3_AGENT_CONF: ['neutron-vpn-agent'],
            neutron_utils.NEUTRON_DHCP_AGENT_CONF: ['neutron-dhcp-agent'],
            neutron_utils.NEUTRON_FWAAS_CONF: ['neutron-vpn-agent'],
            neutron_utils.NEUTRON_METERING_AGENT_CONF:
            ['neutron-metering-agent'],
            neutron_utils.NOVA_CONF: ['nova-api-metadata'],
            neutron_utils.EXT_PORT_CONF: ['ext-port'],
            neutron_utils.PHY_NIC_MTU_CONF: ['os-charm-phy-nic-mtu'],
            neutron_utils.NEUTRON_DHCP_AA_PROFILE_PATH: ['neutron-dhcp-agent'],
            neutron_utils.NEUTRON_OVS_AA_PROFILE_PATH:
                ['neutron-openvswitch-agent'],
            neutron_utils.NEUTRON_L3_AA_PROFILE_PATH: ['neutron-vpn-agent'],
            neutron_utils.NEUTRON_LBAASV2_AA_PROFILE_PATH:
            ['neutron-lbaasv2-agent'],
            neutron_utils.NEUTRON_METADATA_AA_PROFILE_PATH:
            ['neutron-metadata-agent'],
            neutron_utils.NEUTRON_METERING_AA_PROFILE_PATH:
            ['neutron-metering-agent'],
            neutron_utils.NOVA_API_METADATA_AA_PROFILE_PATH:
            ['nova-api-metadata'],
        }
        self.assertEqual(neutron_utils.restart_map(), ex_map)

    @patch.object(neutron_utils, 'get_packages')
    def test_restart_map_ovs_post_trusty(self, mock_get_packages):
        self.config.return_value = 'ovs'
        # No VPN agent after trusty
        mock_get_packages.return_value = ['neutron-l3-agent']
        self.os_release.return_value = 'diablo'
        rmap = neutron_utils.restart_map()
        for services in rmap.values():
            self.assertFalse('neutron-vpn-agent' in services)

    @patch.object(neutron_utils, 'get_packages')
    def test_restart_map_ovs_odl(self, mock_get_packages):
        self.config.return_value = 'ovs-odl'
        mock_get_packages.return_value = ['neutron-vpn-agent']
        self.os_release.return_value = 'icehouse'
        ex_map = {
            neutron_utils.NEUTRON_CONF: ['neutron-lbaas-agent',
                                         'neutron-vpn-agent',
                                         'neutron-dhcp-agent',
                                         'neutron-metering-agent',
                                         'neutron-metadata-agent'],
            neutron_utils.NEUTRON_DNSMASQ_CONF: ['neutron-dhcp-agent'],
            neutron_utils.NEUTRON_LBAAS_AGENT_CONF:
            ['neutron-lbaas-agent'],
            neutron_utils.NEUTRON_METADATA_AGENT_CONF:
            ['neutron-metadata-agent'],
            neutron_utils.NEUTRON_VPNAAS_AGENT_CONF: ['neutron-vpn-agent'],
            neutron_utils.NEUTRON_L3_AGENT_CONF: ['neutron-vpn-agent'],
            neutron_utils.NEUTRON_DHCP_AGENT_CONF: ['neutron-dhcp-agent'],
            neutron_utils.NEUTRON_FWAAS_CONF: ['neutron-vpn-agent'],
            neutron_utils.NEUTRON_METERING_AGENT_CONF:
            ['neutron-metering-agent'],
            neutron_utils.NOVA_CONF: ['nova-api-metadata'],
            neutron_utils.EXT_PORT_CONF: ['ext-port'],
            neutron_utils.PHY_NIC_MTU_CONF: ['os-charm-phy-nic-mtu'],
            neutron_utils.NEUTRON_DHCP_AA_PROFILE_PATH: ['neutron-dhcp-agent'],
            neutron_utils.NEUTRON_LBAAS_AA_PROFILE_PATH:
            ['neutron-lbaas-agent'],
            neutron_utils.NEUTRON_METADATA_AA_PROFILE_PATH:
            ['neutron-metadata-agent'],
            neutron_utils.NEUTRON_METERING_AA_PROFILE_PATH:
            ['neutron-metering-agent'],
            neutron_utils.NOVA_API_METADATA_AA_PROFILE_PATH:
            ['nova-api-metadata'],
        }

        self.assertEqual(neutron_utils.restart_map(), ex_map)

    @patch.object(neutron_utils, 'get_packages')
    def test_restart_map_ovs_odl_newton(self, mock_get_packages):
        self.config.return_value = 'ovs-odl'
        mock_get_packages.return_value = ['neutron-vpn-agent']
        self.os_release.return_value = 'newton'
        ex_map = {
            neutron_utils.NEUTRON_CONF: ['neutron-vpn-agent',
                                         'neutron-lbaasv2-agent',
                                         'neutron-dhcp-agent',
                                         'neutron-metering-agent',
                                         'neutron-metadata-agent'],
            neutron_utils.NEUTRON_DNSMASQ_CONF: ['neutron-dhcp-agent'],
            neutron_utils.NEUTRON_LBAAS_AGENT_CONF:
            ['neutron-lbaasv2-agent'],
            neutron_utils.NEUTRON_METADATA_AGENT_CONF:
            ['neutron-metadata-agent'],
            neutron_utils.NEUTRON_VPNAAS_AGENT_CONF: ['neutron-vpn-agent'],
            neutron_utils.NEUTRON_L3_AGENT_CONF: ['neutron-vpn-agent'],
            neutron_utils.NEUTRON_DHCP_AGENT_CONF: ['neutron-dhcp-agent'],
            neutron_utils.NEUTRON_FWAAS_CONF: ['neutron-vpn-agent'],
            neutron_utils.NEUTRON_METERING_AGENT_CONF:
            ['neutron-metering-agent'],
            neutron_utils.NOVA_CONF: ['nova-api-metadata'],
            neutron_utils.EXT_PORT_CONF: ['ext-port'],
            neutron_utils.PHY_NIC_MTU_CONF: ['os-charm-phy-nic-mtu'],
            neutron_utils.NEUTRON_DHCP_AA_PROFILE_PATH: ['neutron-dhcp-agent'],
            neutron_utils.NEUTRON_LBAASV2_AA_PROFILE_PATH:
            ['neutron-lbaasv2-agent'],
            neutron_utils.NEUTRON_METADATA_AA_PROFILE_PATH:
            ['neutron-metadata-agent'],
            neutron_utils.NEUTRON_METERING_AA_PROFILE_PATH:
            ['neutron-metering-agent'],
            neutron_utils.NOVA_API_METADATA_AA_PROFILE_PATH:
            ['nova-api-metadata'],
        }

        self.assertEqual(neutron_utils.restart_map(), ex_map)

    @patch('charmhelpers.contrib.openstack.templating.OSConfigRenderer')
    def test_register_configs_nsx(self, mock_renderer):
        self.config.return_value = 'nsx'
        self.os_release.return_value = 'diablo'
        configs = neutron_utils.register_configs()
        confs = [neutron_utils.NEUTRON_DHCP_AGENT_CONF,
                 neutron_utils.NEUTRON_METADATA_AGENT_CONF,
                 neutron_utils.NOVA_CONF,
                 neutron_utils.NEUTRON_CONF]
        for conf in confs:
            configs.register.assert_any_call(conf, ANY)

    def test_stop_services_ovs(self):
        self.config.return_value = 'ovs'
        self.os_release.return_value = 'diablo'
        neutron_utils.stop_services()
        calls = [call('neutron-dhcp-agent'),
                 call('neutron-plugin-openvswitch-agent'),
                 call('nova-api-metadata'),
                 call('neutron-l3-agent'),
                 call('neutron-metadata-agent')]
        self.service_stop.assert_has_calls(
            calls,
            any_order=True,
        )

    @patch('charmhelpers.contrib.openstack.templating.OSConfigRenderer')
    def test_register_configs_pre_install(self, mock_renderer):
        self.config.return_value = 'ovs'
        self.is_relation_made.return_value = False
        self.os_release.return_value = 'diablo'
        configs = neutron_utils.register_configs()
        confs = [neutron_utils.NOVA_CONF,
                 neutron_utils.NEUTRON_CONF,
                 neutron_utils.NEUTRON_L3_AGENT_CONF,
                 neutron_utils.NEUTRON_ML2_PLUGIN_CONF,
                 neutron_utils.EXT_PORT_CONF]
        for conf in confs:
            configs.register.assert_any_call(conf, ANY)

    def test_copy_file_without_update(self):
        src = 'dummy_source_dir/dummy_file'
        dst = 'dummy_des_dir'
        neutron_utils.copy_file(src, dst)
        self.assertTrue(self.mkdir.called)
        self.assertTrue(self.copy2.called)

    @patch('neutron_utils.os.path.isfile')
    def test_copy_file_with_update(self, _isfile):
        src = 'dummy_source_dir/dummy_file'
        dst = 'dummy_des_dir'
        _isfile.return_value = False
        neutron_utils.copy_file(src, dst, force=True)
        self.assertTrue(self.mkdir.called)
        self.assertTrue(self.copy2.called)

    @patch('neutron_utils.os.remove')
    @patch('neutron_utils.os.path.isfile')
    def test_remove_file_exists(self, _isfile, _remove):
        path = 'dummy_des_dir/dummy_file'
        _isfile.return_value = True
        neutron_utils.remove_file(path)
        self.assertTrue(_remove.called)
        self.assertFalse(self.log.called)

    @patch('neutron_utils.os.remove')
    @patch('neutron_utils.os.path.isfile')
    def test_remove_file_non_exists(self, _isfile, _remove):
        path = 'dummy_des_dir/dummy_file'
        _isfile.return_value = False
        neutron_utils.remove_file(path)
        self.assertFalse(_remove.called)
        self.assertTrue(self.log.called)

    def test_resolve_config_files_ovs_liberty(self):
        self._set_distrib_codename('trusty')
        self.os_release.return_value = 'liberty'
        self.is_relation_made = False
        actual_map = neutron_utils.resolve_config_files(neutron_utils.OVS,
                                                        'liberty')
        actual_configs = actual_map[neutron_utils.OVS].keys()
        INC_CONFIG = [neutron_utils.NEUTRON_ML2_PLUGIN_CONF]
        EXC_CONFIG = [neutron_utils.NEUTRON_OVS_AGENT_CONF,
                      neutron_utils.NEUTRON_LBAASV2_AA_PROFILE_PATH]
        for config in INC_CONFIG:
            self.assertTrue(config in actual_configs)
        for config in EXC_CONFIG:
            self.assertTrue(config not in actual_configs)

    def test_resolve_config_files_ovs_mitaka(self):
        self._set_distrib_codename('trusty')
        self.os_release.return_value = 'mitaka'
        self.is_relation_made = False
        actual_map = neutron_utils.resolve_config_files(neutron_utils.OVS,
                                                        'mitaka')
        actual_configs = actual_map[neutron_utils.OVS].keys()
        INC_CONFIG = [neutron_utils.NEUTRON_OVS_AGENT_CONF]
        EXC_CONFIG = [neutron_utils.NEUTRON_ML2_PLUGIN_CONF,
                      neutron_utils.NEUTRON_LBAASV2_AA_PROFILE_PATH]
        for config in INC_CONFIG:
            self.assertTrue(config in actual_configs)
        for config in EXC_CONFIG:
            self.assertTrue(config not in actual_configs)

    def test_resolve_config_files_ovs_trusty(self):
        self._set_distrib_codename('trusty')
        self.os_release.return_value = 'mitaka'
        self.is_relation_made = False
        actual_map = neutron_utils.resolve_config_files(neutron_utils.OVS,
                                                        'mitaka')
        actual_configs = actual_map[neutron_utils.OVS].keys()
        INC_CONFIG = [neutron_utils.EXT_PORT_CONF,
                      neutron_utils.PHY_NIC_MTU_CONF,
                      neutron_utils.NEUTRON_LBAAS_AA_PROFILE_PATH]
        for config in INC_CONFIG:
            self.assertTrue(config in actual_configs)

    def test_resolve_config_files_ovs_xenial(self):
        self._set_distrib_codename('xenial')
        self.os_release.return_value = 'mitaka'
        self.is_relation_made = False
        actual_map = neutron_utils.resolve_config_files(neutron_utils.OVS,
                                                        'mitaka')
        actual_configs = actual_map[neutron_utils.OVS].keys()
        EXC_CONFIG = [neutron_utils.EXT_PORT_CONF,
                      neutron_utils.PHY_NIC_MTU_CONF,
                      neutron_utils.NEUTRON_LBAASV2_AA_PROFILE_PATH]
        for config in EXC_CONFIG:
            self.assertTrue(config not in actual_configs)

    def test_resolve_config_files_ovs_newton(self):
        self._set_distrib_codename('xenial')
        self.os_release.return_value = 'newton'
        self.is_relation_made = False
        actual_map = neutron_utils.resolve_config_files(neutron_utils.OVS,
                                                        'newton')
        actual_configs = actual_map[neutron_utils.OVS].keys()
        EXC_CONFIG = [neutron_utils.EXT_PORT_CONF,
                      neutron_utils.PHY_NIC_MTU_CONF,
                      neutron_utils.NEUTRON_LBAAS_AA_PROFILE_PATH]
        for config in EXC_CONFIG:
            self.assertTrue(config not in actual_configs)


network_context = {
    'service_username': 'foo',
    'service_password': 'bar',
    'service_tenant': 'baz',
    'region': 'foo-bar',
    'keystone_host': 'keystone',
    'auth_port': 5000,
    'auth_protocol': 'https'
}


class DummyNetworkServiceContext():

    def __init__(self, return_value):
        self.return_value = return_value

    def __call__(self):
        return self.return_value


class DummyExternalPortContext():

    def __init__(self, return_value):
        self.return_value = return_value

    def __call__(self):
        return self.return_value

cluster1 = ['cluster1-machine1.internal']
cluster2 = ['cluster2-machine1.internal', 'cluster2-machine2.internal'
            'cluster2-machine3.internal']


class TestNeutronAgentReallocation(CharmTestCase):

    def setUp(self):
        if not neutronclient:
            raise self.skipTest('Skipping, no neutronclient installed')
        super(TestNeutronAgentReallocation, self).setUp(neutron_utils,
                                                        TO_PATCH)

    def tearDown(self):
        # Reset cached cache
        hookenv.cache = {}

    def test_assess_status(self):
        with patch.object(neutron_utils, 'assess_status_func') as asf:
            callee = MagicMock()
            asf.return_value = callee
            neutron_utils.assess_status('test-config')
            asf.assert_called_once_with('test-config')
            callee.assert_called_once_with()
            self.os_application_version_set.assert_called_with(
                neutron_utils.VERSION_PACKAGE
            )

    @patch.object(neutron_utils, 'get_optional_interfaces')
    @patch.object(neutron_utils, 'check_optional_relations')
    @patch.object(neutron_utils, 'REQUIRED_INTERFACES')
    @patch.object(neutron_utils, 'services')
    @patch.object(neutron_utils, 'make_assess_status_func')
    def test_assess_status_func(self,
                                make_assess_status_func,
                                services,
                                REQUIRED_INTERFACES,
                                check_optional_relations,
                                get_optional_interfaces):
        services.return_value = ['s1']
        REQUIRED_INTERFACES.copy.return_value = {'int': ['test 1']}
        get_optional_interfaces.return_value = {'opt': ['test 2']}
        neutron_utils.assess_status_func('test-config')
        # ports=None whilst port checks are disabled.
        make_assess_status_func.assert_called_once_with(
            'test-config',
            {'int': ['test 1'], 'opt': ['test 2']},
            charm_func=check_optional_relations, services=['s1'], ports=None)

    def test_pause_unit_helper(self):
        with patch.object(neutron_utils, '_pause_resume_helper') as prh:
            neutron_utils.pause_unit_helper('random-config')
            prh.assert_called_once_with(neutron_utils.pause_unit,
                                        'random-config')
        with patch.object(neutron_utils, '_pause_resume_helper') as prh:
            neutron_utils.resume_unit_helper('random-config')
            prh.assert_called_once_with(neutron_utils.resume_unit,
                                        'random-config')

    @patch.object(neutron_utils, 'services')
    def test_pause_resume_helper(self, services):
        f = MagicMock()
        services.return_value = ['s1']
        with patch.object(neutron_utils, 'assess_status_func') as asf:
            asf.return_value = 'assessor'
            neutron_utils._pause_resume_helper(f, 'some-config')
            asf.assert_called_once_with('some-config')
            # ports=None whilst port checks are disabled.
            f.assert_called_once_with('assessor', services=['s1'], ports=None)

    @patch.object(neutron_utils, 'subprocess')
    @patch.object(neutron_utils, 'shutil')
    @patch('os.path.exists')
    def test_install_systemd_override_systemd(self, _os_exists, _shutil,
                                              _subprocess):
        '''
        Ensure systemd override is only installed on systemd based systems
        '''
        self.init_is_systemd.return_value = True
        _os_exists.return_value = False
        neutron_utils.install_systemd_override()
        _os_exists.assert_called_with(
            '/etc/systemd/system/nova-api-metadata.service.d/override.conf'
        )
        self.mkdir.assert_called_with(
            '/etc/systemd/system/nova-api-metadata.service.d'
        )
        _shutil.copy.assert_called_with(
            'files/override.conf',
            '/etc/systemd/system/nova-api-metadata.service.d/override.conf'
        )
        _subprocess.check_call.assert_called_with(
            ['systemctl', 'daemon-reload']
        )

    @patch.object(neutron_utils, 'context')
    def test_configure_apparmor_mitaka(self, context):
        self.os_release.return_value = 'mitaka'
        context.AppArmorContext = MagicMock()
        neutron_utils.configure_apparmor()
        context.AppArmorContext.assert_any_call(
            neutron_utils.NEUTRON_LBAAS_AA_PROFILE
        )

    @patch.object(neutron_utils, 'context')
    def test_configure_apparmor_newton(self, context):
        self.os_release.return_value = 'newton'
        context.AppArmorContext = MagicMock()
        neutron_utils.configure_apparmor()
        context.AppArmorContext.assert_any_call(
            neutron_utils.NEUTRON_LBAASV2_AA_PROFILE
        )
