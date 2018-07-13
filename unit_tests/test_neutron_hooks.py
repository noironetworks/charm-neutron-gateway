import sys

from mock import MagicMock, patch, call

# python-apt is not installed as part of test-requirements but is imported by
# some charmhelpers modules so create a fake import.
sys.modules['apt'] = MagicMock()
sys.modules['apt_pkg'] = MagicMock()

import charmhelpers.core.hookenv as hookenv
with patch('charmhelpers.core.hookenv.config'):
    with patch('neutron_utils.restart_map'):
        with patch('neutron_utils.register_configs'):
            with patch('charmhelpers.contrib.'
                       'hardening.harden.harden') as mock_dec:
                mock_dec.side_effect = (lambda *dargs, **dkwargs: lambda f:
                                        lambda *args, **kwargs:
                                        f(*args, **kwargs))
                import neutron_hooks as hooks

from test_utils import CharmTestCase


TO_PATCH = [
    'config',
    'configure_installation_source',
    'valid_plugin',
    'apt_update',
    'apt_install',
    'apt_purge',
    'filter_installed_packages',
    'get_early_packages',
    'get_packages',
    'log',
    'do_openstack_upgrade',
    'openstack_upgrade_available',
    'CONFIGS',
    'configure_ovs',
    'relation_set',
    'relation_ids',
    'relation_get',
    'install_ca_cert',
    'execd_preinstall',
    'lsb_release',
    'stop_services',
    'b64decode',
    'create_sysctl',
    'update_nrpe_config',
    'update_legacy_ha_files',
    'install_legacy_ha_files',
    'cache_env_data',
    'get_hacluster_config',
    'remove_legacy_ha_files',
    'cleanup_ovs_netns',
    'stop_neutron_ha_monitor_daemon',
    'use_l3ha',
    'kv',
    'service_restart',
    'is_unit_paused_set',
    'install_systemd_override',
    'configure_apparmor',
]


class TestQuantumHooks(CharmTestCase):

    def setUp(self):
        super(TestQuantumHooks, self).setUp(hooks, TO_PATCH)
        self.config.side_effect = self.test_config.get
        self.test_config.set('openstack-origin', 'cloud:precise-havana')
        self.test_config.set('plugin', 'ovs')
        self.lsb_release.return_value = {'DISTRIB_CODENAME': 'precise'}
        # passthrough
        self.b64decode.side_effect = lambda arg: arg
        hookenv.config.side_effect = self.test_config.get
        hooks.hooks._config_save = False

    def _call_hook(self, hookname):
        hooks.hooks.execute([
            'hooks/{}'.format(hookname)])

    def test_install_hook(self):
        self.valid_plugin.return_value = True
        _pkgs = ['foo', 'bar']
        self.filter_installed_packages.return_value = _pkgs
        self._call_hook('install')
        self.configure_installation_source.assert_called_with(
            'cloud:precise-havana'
        )
        self.apt_update.assert_called_with(fatal=True)
        self.apt_install.assert_has_calls([
            call(_pkgs, fatal=True),
            call(_pkgs, fatal=True),
        ])
        self.assertTrue(self.get_early_packages.called)
        self.assertTrue(self.get_packages.called)
        self.assertTrue(self.execd_preinstall.called)
        self.assertTrue(self.install_systemd_override.called)

    def test_install_hook_precise_nocloudarchive(self):
        self.test_config.set('openstack-origin', 'distro')
        self._call_hook('install')
        self.configure_installation_source.assert_called_with(
            'cloud:precise-icehouse'
        )

    @patch('sys.exit')
    def test_install_hook_invalid_plugin(self, _exit):
        self.valid_plugin.return_value = False
        self._call_hook('install')
        self.assertTrue(self.log.called)
        _exit.assert_called_with(1)

    def test_config_changed(self):
        def mock_relids(rel):
            return ['relid']
        self.test_config.set('sysctl', '{ kernel.max_pid: "1337"}')
        self.openstack_upgrade_available.return_value = True
        self.valid_plugin.return_value = True
        self.relation_ids.side_effect = mock_relids
        _amqp_joined = self.patch('amqp_joined')
        _amqp_nova_joined = self.patch('amqp_nova_joined')
        self._call_hook('config-changed')
        self.assertTrue(self.do_openstack_upgrade.called)
        self.assertTrue(self.configure_ovs.called)
        self.assertTrue(_amqp_joined.called)
        self.assertTrue(_amqp_nova_joined.called)
        self.assertTrue(self.create_sysctl.called)
        self.configure_apparmor.assert_called_with()

    def test_config_changed_upgrade(self):
        self.openstack_upgrade_available.return_value = True
        self.valid_plugin.return_value = True
        self._call_hook('config-changed')
        self.assertTrue(self.do_openstack_upgrade.called)
        self.assertTrue(self.configure_ovs.called)

    def test_config_changed_n1kv(self):
        self.openstack_upgrade_available.return_value = False
        self.valid_plugin.return_value = True
        self.filter_installed_packages.side_effect = lambda p: p
        self.test_config.set('plugin', 'n1kv')
        self._call_hook('config-changed')
        self.apt_install.assert_called_with('neutron-l3-agent')
        self.test_config.set('enable-l3-agent', False)
        self._call_hook('config-changed')
        self.apt_purge.assert_called_with('neutron-l3-agent')

    @patch('sys.exit')
    def test_config_changed_invalid_plugin(self, _exit):
        self.valid_plugin.return_value = False
        self._call_hook('config-changed')
        self.assertTrue(self.log.called)
        _exit.assert_called_with(1)

    def test_upgrade_charm(self):
        _install = self.patch('install')
        _config_changed = self.patch('config_changed')
        self._call_hook('upgrade-charm')
        self.assertTrue(_install.called)
        self.assertTrue(_config_changed.called)
        self.assertTrue(self.install_systemd_override.called)

    def test_amqp_joined(self):
        self._call_hook('amqp-relation-joined')
        self.relation_set.assert_called_with(
            username='neutron',
            vhost='openstack',
            relation_id=None
        )

    def test_amqp_changed(self):
        self._call_hook('amqp-relation-changed')
        self.assertTrue(self.CONFIGS.write_all.called)

    def test_amqp_departed_no_rel(self):
        self.CONFIGS.complete_contexts.return_value = []
        self._call_hook('amqp-relation-departed')
        self.assertFalse(self.CONFIGS.write_all.called)

    def test_amqp_departed(self):
        self.CONFIGS.complete_contexts.return_value = ['amqp']
        self._call_hook('amqp-relation-departed')
        self.assertTrue(self.CONFIGS.write_all.called)

    def test_amqp_nova_joined(self):
        self._call_hook('amqp-nova-relation-joined')
        self.relation_set.assert_called_with(
            username='nova',
            vhost='openstack',
            relation_id=None
        )

    def test_amqp_nova_changed_no_rel(self):
        self.CONFIGS.complete_contexts.return_value = []
        self._call_hook('amqp-nova-relation-changed')
        self.assertFalse(self.CONFIGS.write_all.called)

    def test_amqp_nova_changed(self):
        self.CONFIGS.complete_contexts.return_value = ['amqp-nova']
        self._call_hook('amqp-nova-relation-changed')
        self.assertTrue(self.CONFIGS.write_all.called)

    def test_nm_changed(self):
        def _relation_get(key):
            data = {
                'ca_cert': 'cert',
                'restart_trigger': None,
            }
            return data.get(key)
        self.relation_get.side_effect = _relation_get
        self._call_hook('quantum-network-service-relation-changed')
        self.assertTrue(self.CONFIGS.write_all.called)
        self.install_ca_cert.assert_called_with('cert')

    def test_nm_changed_restart_nonce(self):
        '''Ensure first set of restart_trigger restarts nova-api-metadata'''
        def _relation_get(key):
            data = {
                'ca_cert': 'cert',
                'restart_trigger': '1111111222222333333',
            }
            return data.get(key)
        self.relation_get.side_effect = _relation_get
        self.is_unit_paused_set.return_value = False
        kv_mock = MagicMock()
        self.kv.return_value = kv_mock
        kv_mock.get.return_value = None
        self._call_hook('quantum-network-service-relation-changed')
        self.assertTrue(self.CONFIGS.write_all.called)
        self.install_ca_cert.assert_called_with('cert')
        self.service_restart.assert_called_with('nova-api-metadata')
        kv_mock.get.assert_called_with('restart_nonce')
        kv_mock.set.assert_called_with('restart_nonce',
                                       '1111111222222333333')
        self.assertTrue(kv_mock.flush.called)

    def test_nm_changed_restart_nonce_changed(self):
        '''Ensure change of restart_trigger restarts nova-api-metadata'''
        def _relation_get(key):
            data = {
                'ca_cert': 'cert',
                'restart_trigger': '1111111222222333333',
            }
            return data.get(key)
        self.relation_get.side_effect = _relation_get
        self.is_unit_paused_set.return_value = False
        kv_mock = MagicMock()
        self.kv.return_value = kv_mock
        kv_mock.get.return_value = ('22222233333344444')
        self._call_hook('quantum-network-service-relation-changed')
        self.assertTrue(self.CONFIGS.write_all.called)
        self.install_ca_cert.assert_called_with('cert')
        self.service_restart.assert_called_with('nova-api-metadata')
        kv_mock.get.assert_called_with('restart_nonce')
        kv_mock.set.assert_called_with('restart_nonce',
                                       '1111111222222333333')
        self.assertTrue(kv_mock.flush.called)

    def test_nm_changed_restart_nonce_nochange(self):
        '''Ensure no change in restart_trigger skips restarts'''
        def _relation_get(key):
            data = {
                'ca_cert': 'cert',
                'restart_trigger': '1111111222222333333',
            }
            return data.get(key)
        self.relation_get.side_effect = _relation_get
        self.is_unit_paused_set.return_value = False
        kv_mock = MagicMock()
        self.kv.return_value = kv_mock
        kv_mock.get.return_value = ('1111111222222333333')
        self._call_hook('quantum-network-service-relation-changed')
        self.assertTrue(self.CONFIGS.write_all.called)
        self.install_ca_cert.assert_called_with('cert')
        self.assertFalse(self.service_restart.called)
        kv_mock.get.assert_called_with('restart_nonce')
        self.assertFalse(kv_mock.set.called)
        self.assertFalse(kv_mock.flush.called)

    def test_neutron_plugin_changed(self):
        self.use_l3ha.return_value = True
        self._call_hook('neutron-plugin-api-relation-changed')
        self.apt_install.assert_called_with(['keepalived', 'conntrack'],
                                            fatal=True)
        self.assertTrue(self.CONFIGS.write_all.called)

    def test_cluster_departed_nvp(self):
        self.test_config.set('plugin', 'nvp')
        self._call_hook('cluster-relation-departed')
        self.assertTrue(self.log.called)

    def test_stop(self):
        self._call_hook('stop')
        self.assertTrue(self.stop_services.called)

    def test_ha_relation_joined(self):
        self.test_config.set('ha-legacy-mode', True)
        self._call_hook('ha_relation_joined')
        self.assertTrue(self.cache_env_data.called)
        self.assertTrue(self.get_hacluster_config.called)
        self.assertTrue(self.install_legacy_ha_files.called)

    def test_ha_relation_departed(self):
        self.test_config.set('ha-legacy-mode', True)
        self._call_hook('ha-relation-departed')
        self.assertTrue(self.remove_legacy_ha_files.called)
        self.assertTrue(self.stop_neutron_ha_monitor_daemon.called)

    def test_quantum_network_service_relation_changed(self):
        self.test_config.set('ha-legacy-mode', True)
        self._call_hook('quantum-network-service-relation-changed')
        self.assertTrue(self.cache_env_data.called)
