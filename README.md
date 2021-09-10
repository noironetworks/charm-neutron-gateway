# Overview

The neutron-gateway charm deploys the data plane of
[Neutron][upstream-neutron], the core OpenStack service that provides software
defined networking (SDN) for Nova instances. This provides the Neutron Gateway
service, which in turn supplies two key services: L3 network routing and DHCP.
The charm works alongside other Juju-deployed OpenStack applications; in
particular: neutron-openvswitch, nova-compute, and nova-cloud-controller.

> **Note**: Starting with OpenStack Train, the neutron-gateway and
  neutron-openvswitch charm combination can be replaced by the [OVN
  charms][cdg-ovn] (e.g. ovn-central, ovn-chassis, and neutron-api-plugin-ovn).

# Usage

## Configuration

This section covers common and/or important configuration options. See file
`config.yaml` for the full list of options, along with their descriptions and
default values. See the [Juju documentation][juju-docs-config-apps] for details
on configuring applications.

#### `data-port`

A bridge that Neutron Gateway will bind to, given in the form of a
space-delimited bridge:port mapping (e.g. 'br-ex:ens8'). The port will be added
to its corresponding bridge.

> **Note**: If network device names are not consistent between hosts (e.g.
  'eth1' and 'ens8') a list of values can be provided where a MAC address is
  used in the place of a device name. The charm will iterate through the list
  and configure the first matching interface.

The specified bridge(s) should match the one(s) defined in the
`bridge-mappings` option.

Flat or VLAN network types are supported.

The device itself must not have any L3 configuration. In MAAS, it must have an
IP mode of 'Unconfigured'.

#### `bridge-mappings`

A space-delimited list of ML2 data provider:bridge mappings (e.g.
'physnet1:br-ex'). The specified bridge(s) should match the one(s) defined in
the `data-port` option.

#### `openstack-origin`

The `openstack-origin` option states the software sources. A common value is an
OpenStack UCA release (e.g. 'cloud:bionic-ussuri' or 'cloud:focal-victoria').
See [Ubuntu Cloud Archive][wiki-uca]. The underlying host's existing apt
sources will be used if this option is not specified (this behaviour can be
explicitly chosen by using the value of 'distro').

## Deployment

These deployment instructions assume the following pre-existing applications:
neutron-api, nova-cloud-controller, and rabbitmq-server.

> **Important**: For Neutron Gateway to function properly, the
  nova-cloud-controller charm must have its `network-manager` option set to
  'Neutron'.

Deploy Neutron Gateway:

    juju deploy neutron-gateway
    juju add-relation neutron-gateway:quantum-network-service nova-cloud-controller:quantum-network-service
    juju add-relation neutron-gateway:neutron-plugin-api neutron-api:neutron-plugin-api
    juju add-relation neutron-gateway:amqp rabbitmq-server:amqp

### Port configuration

Network ports are configured with the `bridge-mappings` and `data-port` options
but the neutron-api charm also has several relevant options (e.g.
`flat-network-providers`, `vlan-ranges`, etc.). Additionally, the network
topology can be further defined with supplementary `openstack` client commands.

<!-- The two trailing spaces for each of the below three example headers is
deliberate. -->

**Example 1**  
This configuration has a single external network and is typically used when
floating IP addresses are combined with a GRE private network.

Charm option values (YAML):

    neutron-gateway:
        bridge-mappings: physnet1:br-ex
        data-port: br-ex:eth1
    neutron-api:
        flat-network-providers: physnet1

Supplementary commands:

    openstack network create --provider-network-type flat \
       --provider-physical-network physnet1 --external \
       external
    openstack router set router1 --external-gateway external

**Example 2**  
This configuration is for two networks, where an internal private network is
directly connected to the gateway with public IP addresses but a floating IP
address range is also offered.

Charm option values (YAML):

    neutron-gateway:
        bridge-mappings: physnet1:br-data external:br-ex
        data-port: br-data:eth1 br-ex:eth2
    neutron-api:
        flat-network-providers: physnet1 external

**Example 3**  
This configuration has two external networks, where one is for public instance
addresses and one is for floating IP addresses. Both networks are on the same
physical network connection (but they might be on different VLANs).

Charm option values (YAML):

    neutron-gateway:
        bridge-mappings: physnet1:br-data
        data-port: br-data:eth1
    neutron-api:
        flat-network-providers: physnet1

Supplementary commands:

    openstack network create --provider-network-type vlan \
       --provider-segment 400 \
       --provider-physical-network physnet1 --share \
       external
    openstack network create --provider-network-type vlan \
       --provider-segment 401 \
       --provider-physical-network physnet1 --share --external \
       floating
    openstack router set router1 --external-gateway floating

#### legacy `ext-port` option

The `ext-port` option is deprecated and is superseded by the `data-port`
option. The `ext-port` option always created a bridge called 'br-ex' for
external networks that was used implicitly by external router interfaces.

The following will occur if both the `data-port` and `ext-port` options are
set:

* the neutron-gateway unit will be marked as 'blocked' to indicate that the
  charm is misconfigured
* the `ext-port` option will be ignored
* a warning will be logged

## Instance MTU

When using Open vSwitch plugin with GRE tunnels the default MTU of 1500 can
cause packet fragmentation due to GRE overhead. One solution to this problem is
to increase the MTU on physical hosts and network equipment. When this is not
feasible the charm's `instance-mtu` option can be used to reduce instance MTU
via DHCP:

    juju config neutron-gateway instance-mtu=1400

> **Note**: The `instance-mtu` option is supported starting with OpenStack
  Havana.

## Actions

This section covers Juju [actions][juju-docs-actions] supported by the charm.
Actions allow specific operations to be performed on a per-unit basis. To
display action descriptions run `juju actions --schema neutron-gateway`. If the
charm is not deployed then see file `actions.yaml`.

* `cleanup`
* `get-status-dhcp`
* `get-status-lb`
* `get-status-routers`
* `openstack-upgrade`
* `pause`
* `restart-services`
* `resume`
* `restart-services`
* `run-deferred-hooks`
* `security-checklist`
* `show-deferred-events`

## Deferred service events

Operational or maintenance procedures applied to a cloud often lead to the
restarting of various OpenStack services and/or the calling of certain charm
hooks. Although normal, such events can be undesirable due to the service
interruptions they can cause.

The deferred service events feature provides the operator the choice of
preventing these service restarts and hook calls from occurring, which can then
be resolved at a more opportune time.

See the [Deferred service events][cdg-deferred-service-events] page in the
[OpenStack Charms Deployment Guide][cdg] for an in-depth treatment of this
feature.

# Documentation

The OpenStack Charms project maintains two documentation guides:

* [OpenStack Charm Guide][cg]: for project information, including development
  and support notes
* [OpenStack Charms Deployment Guide][cdg]: for charm usage information

# Bugs

Please report bugs on [Launchpad][lp-bugs-charm-neutron-gateway].

<!-- LINKS -->

[cg]: https://docs.openstack.org/charm-guide
[cdg]: https://docs.openstack.org/project-deploy-guide/charm-deployment-guide
[cdg-deferred-service-events]: https://docs.openstack.org/project-deploy-guide/charm-deployment-guide/latest/deferred-events.html
[lp-bugs-charm-neutron-gateway]: https://bugs.launchpad.net/charm-neutron-gateway/+filebug
[juju-docs-config-apps]: https://juju.is/docs/configuring-applications
[upstream-neutron]: https://docs.openstack.org/neutron/latest/
[juju-docs-actions]: https://jaas.ai/docs/actions
[cdg-ovn]: https://docs.openstack.org/project-deploy-guide/charm-deployment-guide/latest/app-ovn.html
[wiki-uca]: https://wiki.ubuntu.com/OpenStack/CloudArchive
