Overview
--------

Neutron provides flexible software defined networking (SDN) for OpenStack.

This charm is designed to be used in conjunction with the rest of the OpenStack
related charms in the charm store to virtualize the network that Nova Compute
instances plug into.

Neutron supports a rich plugin/extension framework for propriety networking
solutions and supports (in core) Nicira NVP, NEC, Cisco and others...

See the upstream [Neutron documentation](http://docs.openstack.org/trunk/openstack-network/admin/content/use_cases_single_router.html)
for more details.

Usage
-----

In order to use Neutron with OpenStack, you will need to deploy the
nova-compute and nova-cloud-controller charms with the network-manager
configuration set to 'Neutron':

    nova-cloud-controller:
        network-manager: Neutron

This decision must be made prior to deploying OpenStack with Juju as
Neutron is deployed baked into these charms from install onwards:

    juju deploy nova-compute
    juju deploy --config config.yaml nova-cloud-controller
    juju deploy neutron-api
    juju add-relation nova-compute nova-cloud-controller
    juju add-relation neutron-api nova-cloud-controller

The Neutron Gateway can then be added to the deploying:

    juju deploy neutron-gateway
    juju add-relation neutron-gateway mysql
    juju add-relation neutron-gateway rabbitmq-server
    juju add-relation neutron-gateway nova-cloud-controller
    juju add-relation neutron-gateway neutron-api

The gateway provides two key services; L3 network routing and DHCP services.

These are both required in a fully functional Neutron OpenStack deployment.

See upstream [Neutron multi extnet](http://docs.openstack.org/trunk/config-reference/content/adv_cfg_l3_agent_multi_extnet.html)

Configuration Options
---------------------

Port Configuration
==================

All network types (internal, external) are configured with bridge-mappings and
data-port and the flat-network-providers configuration option of the
neutron-api charm.  Once deployed, you can configure the network specifics
using neutron net-create.

If the device name is not consistent between hosts, you can specify the same
bridge multiple times with MAC addresses instead of interface names.  The charm
will loop through the list and configure the first matching interface.

Basic configuration of a single external network, typically used as floating IP
addresses combined with a GRE private network:

    neutron-gateway:
        bridge-mappings:         physnet1:br-ex
        data-port:               br-ex:eth1
    neutron-api:
        flat-network-providers:  physnet1

    neutron net-create --provider:network_type flat \
        --provider:physical_network physnet1 --router:external=true \
        external
    neutron router-gateway-set provider external

Alternative configuration with two networks, where the internal private
network is directly connected to the gateway with public IP addresses but a
floating IP address range is also offered.

    neutron-gateway:
        bridge-mappings:         physnet1:br-data external:br-ex
        data-port:               br-data:eth1 br-ex:eth2
    neutron-api:
        flat-network-providers:  physnet1 external

Alternative configuration with two external networks, one for public instance
addresses and one for floating IP addresses.  Both networks are on the same
physical network connection (but they might be on different VLANs, that is
configured later using neutron net-create).

    neutron-gateway:
        bridge-mappings:         physnet1:br-data
        data-port:               br-data:eth1
    neutron-api:
        flat-network-providers:  physnet1

    neutron net-create --provider:network_type vlan \
        --provider:segmentation_id 400 \
        --provider:physical_network physnet1 --shared external
    neutron net-create --provider:network_type vlan \
        --provider:segmentation_id 401 \
        --provider:physical_network physnet1 --shared --router:external=true \
        floating
    neutron router-gateway-set provider floating

This replaces the previous system of using ext-port, which always created a bridge
called br-ex for external networks which was used implicitly by external router
interfaces.

Instance MTU
============

When using Open vSwitch plugin with GRE tunnels default MTU of 1500 can cause
packet fragmentation due to GRE overhead. One solution is to increase the MTU on
physical hosts and network equipment. When this is not possible or practical the
charm's instance-mtu option can be used to reduce instance MTU via DHCP.

    juju set neutron-gateway instance-mtu=1400

OpenStack upstream documentation recommends a MTU value of 1400:
[OpenStack documentation](http://docs.openstack.org/admin-guide-cloud/content/openvswitch_plugin.html)

Note that this option was added in Havana and will be ignored in older releases.
