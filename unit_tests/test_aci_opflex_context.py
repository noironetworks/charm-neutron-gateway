
import io

from contextlib import contextmanager

from mock import (
    MagicMock,
    patch
)
import aci_opflex_context
#import neutron_contexts

from test_utils import (
    CharmTestCase
)

TO_PATCH = [
    'config',
    'unit_get',
    'gethostname'
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


class TestAciOpflexConfigContext(CharmTestCase):

    def setUp(self):
        super(TestAciOpflexConfigContext, self).setUp(aci_opflex_context,
                                              TO_PATCH)
        self.config.side_effect = self.test_config.get

    def test_opflex_encap_vxlan(self):
        self.test_config.set('aci-opflex-debug-level', 2)
        self.test_config.set('aci-apic-system-id', 'utest')
        self.test_config.set('aci-opflex-peer-ip', '1.2.3.4')
        self.test_config.set('aci-encap', 'vxlan')
        self.test_config.set('aci-uplink-interface', 'ens10')
        self.test_config.set('aci-infra-vlan', 1234)
        self.test_config.set('aci-opflex-remote-ip', '4.5.6.7')
        self.gethostname.return_value = 'ciscoaci-host'
        self.assertEqual(aci_opflex_context.AciOpflexConfigContext()(),
                         {'debug_level': 2,
                          'apic_system_id': 'utest',
                          'opflex_peer_ip': '1.2.3.4',
                          'aci_encap': 'vxlan',
                          'opflex_uplink_iface': 'ens10',
                          'aci_infra_vlan': 1234,
                          'opflex_remote_ip': '4.5.6.7',
                          'opflex_encap_iface': 'br-fab_vxlan0',
                          'ovs_bridge': 'br-int',
                          'hostname': 'ciscoaci-host'})

    def test_opflex_encap_vlan(self):
        self.test_config.set('aci-opflex-debug-level', 2)
        self.test_config.set('aci-apic-system-id', 'utest')
        self.test_config.set('aci-opflex-peer-ip', '1.2.3.4')
        self.test_config.set('aci-encap', 'vlan')
        self.test_config.set('aci-uplink-interface', 'ens10')
        self.test_config.set('aci-infra-vlan', 1234)
        self.test_config.set('aci-opflex-remote-ip', '4.5.6.7')
        self.gethostname.return_value = 'ciscoaci-host'
        self.assertEqual(aci_opflex_context.AciOpflexConfigContext()(),
                         {'debug_level': 2,
                          'apic_system_id': 'utest',
                          'opflex_peer_ip': '1.2.3.4',
                          'aci_encap': 'vlan',
                          'opflex_uplink_iface': 'ens10',
                          'aci_infra_vlan': 1234,
                          'opflex_remote_ip': '4.5.6.7',
                          'opflex_encap_iface': '',
                          'ovs_bridge': 'br-int',
                          'hostname': 'ciscoaci-host'})
