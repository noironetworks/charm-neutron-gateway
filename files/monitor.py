# Copyright 2014 Canonical Ltd.
#
# Authors: Hui Xiang <hui.xiang@canonical.com>
#

"""
Helpers for monitoring Neutron agents, reschedule failed agents,
cleaned resources on failed nodes.
"""


import os
import signal
import sys
import socket
import subprocess
import time

from oslo.config import cfg
from neutron.agent.linux import ovs_lib
from neutron.agent.linux import ip_lib
from neutron.openstack.common import log as logging

LOG = logging.getLogger(__name__)


class Daemon(object):
    """A generic daemon class.

    Usage: subclass the Daemon class and override the run() method
    """
    def __init__(self, stdin='/dev/null', stdout='/dev/null',
                 stderr='/dev/null', procname='python', uuid=None):
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.procname = procname

    def _fork(self):
        try:
            pid = os.fork()
            if pid > 0:
                sys.exit(0)
        except OSError:
            LOG.exception('Fork failed')
            sys.exit(1)

    def daemonize(self):
        """Daemonize process by doing Stevens double fork."""
        # fork first time
        self._fork()

        # decouple from parent environment
        os.chdir("/")
        os.setsid()
        os.umask(0)
        # fork second time
        self._fork()

        # redirect standard file descriptors
        sys.stdout.flush()
        sys.stderr.flush()
        stdin = open(self.stdin, 'r')
        stdout = open(self.stdout, 'a+')
        stderr = open(self.stderr, 'a+', 0)
        os.dup2(stdin.fileno(), sys.stdin.fileno())
        os.dup2(stdout.fileno(), sys.stdout.fileno())
        os.dup2(stderr.fileno(), sys.stderr.fileno())

        signal.signal(signal.SIGTERM, self.handle_sigterm)

    def handle_sigterm(self, signum, frame):
        sys.exit(0)

    def start(self):
        """Start the daemon."""
        self.daemonize()
        self.run()

    def run(self):
        """Override this method when subclassing Daemon.

        start() will call this method after the process has daemonized.
        """
        pass


class MonitorNeutronAgentsDaemon(Daemon):
    def __init__(self):
        super(MonitorNeutronAgentsDaemon, self).__init__()
        logging.setup('Neuron-HA-Monitor')
        LOG.info('Monitor Neutron Agent Loop Init')
        self.hostname = None
        self.env = {}

    def get_env(self):
        envrc_f = '/etc/legacy_ha_envrc'
        envrc_f_m = False
        if os.path.isfile(envrc_f):
            ctime = time.ctime(os.stat(envrc_f).st_ctime)
            mtime = time.ctime(os.stat(envrc_f).st_mtime)
            if ctime != mtime:
                envrc_f_m = True

            if not self.env or envrc_f_m:
                with open(envrc_f, 'r') as f:
                    for line in f:
                        data = line.strip().split('=')
                        if data and data[0] and data[1]:
                            self.env[data[0]] = data[1]
                        else:
                            raise Exception("OpenStack env data uncomplete.")
        return self.env

    def get_hostname(self):
        if not self.hostname:
            self.hostname = socket.gethostname()
        return self.hostname

    def get_root_helper(self):
        return 'sudo'

    def list_nodes(self):
        cmd = ['crm', 'node', 'list']
        out = subprocess.check_output(cmd)
        nodes = []
        for line in str(out).split('\n'):
            if line!='' and line.find('offline')==-1:
                nodes.append(line.split(':')[0])
        return nodes

    def get_crm_no_1_node(self):
        nodes = self.list_nodes()
        if nodes:
            return nodes[0].split('(')[0] or nodes[0]
        else:
            LOG.error('Failed to get crm node list.')
            return None

    def unplug_device(self, device):
        try:
            device.link.delete()
        except RuntimeError:
            root_helper = self.get_root_helper()
            # Maybe the device is OVS port, so try to delete
            bridge_name = ovs_lib.get_bridge_for_iface(root_helper,
                                                       device.name)
            if bridge_name:
                bridge = ovs_lib.OVSBridge(bridge_name, root_helper)
                bridge.delete_port(device.name)
            else:
                LOG.debug('Unable to find bridge for device: %s', device.name)

    def cleanup(self):
        self.cleanup_dhcp(None)
        self.cleanup_router(None)

    def cleanup_dhcp(self, networks):
        namespaces = []
        if networks:
            for network, agent in networks.iteritems():
                namespaces.append('qdhcp-' + network)
        else:
            cmd = 'sudo ip netns | grep qdhcp'
            try:
                qns = subprocess.check_output(cmd, shell=True).strip().split(' ')
                for qn in qns:
                    namespaces.append(qn)
            except Exception:
                LOG.error('No dhcp namespaces found.')

        if namespaces:
            LOG.info('Namespaces: %s is going to be deleted.' % namespaces)
            self.destroy_namespaces(namespaces)

    def cleanup_router(self, routers):
        namespaces = []
        if routers:
            for router, agent in routers.iteritems():
                namespaces.append('qrouter-' + router)
        else:
            cmd = 'sudo ip netns | grep qrouter'
            try:
                qns = subprocess.check_output(cmd, shell=True).strip().split(' ')
                for qn in qns:
                    namespaces.append(qn)
            except Exception:
                LOG.error('No router namespaces found.')

        if namespaces:
            LOG.info('Namespaces: %s is going to be deleted.' % namespaces)
            self.destroy_namespaces(namespaces)

    def destroy_namespaces(self, namespaces):
        try:
            root_helper = self.get_root_helper()
            for namespace in namespaces:
                ip = ip_lib.IPWrapper(root_helper, namespace)
                if ip.netns.exists(namespace):
                    for device in ip.get_devices(exclude_loopback=True):
                        self.unplug_device(device)

            ip.garbage_collect_namespace()
        except Exception:
            LOG.exception('Error unable to destroy namespace: %s', namespace)

    def is_same_host(self, host):
        return str(host).strip() == self.get_hostname()

    def validate_reschedule(self):
        crm_no_1_node = self.get_crm_no_1_node()
        if not crm_no_1_node:
            LOG.error('No crm first node could be found.')
            return False

        if not self.is_same_host(crm_no_1_node):
            LOG.warn('Only the first crm node %s could reschedule. '
                     % crm_no_1_node)
            return False
        return True

    def l3_agents_reschedule(self, l3_agents, routers, quantum):
        if not self.validate_reschedule():
            return

        index = 0
        for router_id in routers:
            agent = index % len(l3_agents)
            LOG.info('Moving router %s from %s to %s' %
                     (router_id, routers[router_id], l3_agents[agent]))
            quantum.remove_router_from_l3_agent(l3_agent=routers[router_id],
                                                router_id=router_id)
            quantum.add_router_to_l3_agent(l3_agent=l3_agents[agent],
                                           body={'router_id': router_id})
            index += 1

    def dhcp_agents_reschedule(self, dhcp_agents, networks, quantum):
        if not self.validate_reschedule():
            return

        index = 0
        for network_id in networks:
            agent = index % len(dhcp_agents)
            LOG.info('Moving network %s from %s to %s' % (network_id,
                     networks[network_id], dhcp_agents[agent]))
            quantum.remove_network_from_dhcp_agent(
                dhcp_agent=networks[network_id], network_id=network_id)
            quantum.add_network_to_dhcp_agent(
                dhcp_agent=dhcp_agents[agent],
                body={'network_id': network_id})
            index += 1

    def reassign_agent_resources(self):
        ''' Use agent scheduler API to detect down agents and re-schedule '''
        DHCP_AGENT = "DHCP Agent"
        L3_AGENT = "L3 Agent"
        env = self.get_env()
        if not env:
            LOG.info('Unable to re-assign resources at this time')
            return
        try:
            from quantumclient.v2_0 import client
        except ImportError:
            ''' Try to import neutronclient instead for havana+ '''
            from neutronclient.v2_0 import client

        auth_url = '%(auth_protocol)s://%(keystone_host)s:%(auth_port)s/v2.0' \
                   % env
        quantum = client.Client(username=env['service_username'],
                                password=env['service_password'],
                                tenant_name=env['service_tenant'],
                                auth_url=auth_url,
                                region_name=env['region'])

        try:
            agents = quantum.list_agents(agent_type=DHCP_AGENT)
        except Exception:
            self.cleanup()
            LOG.error('Failed to get neutron agent list,'
                      'might be network lost connection,'
                      'clean up neutron resources.')
            return

        dhcp_agents = []
        l3_agents = []
        networks = {}
        for agent in agents['agents']:
            hosted_networks = quantum.list_networks_on_dhcp_agent(
                agent['id'])['networks']
            if not agent['alive']:
                LOG.info('DHCP Agent %s down' % agent['id'])
                for network in hosted_networks:
                    networks[network['id']] = agent['id']
                if self.is_same_host(agent['host']):
                    self.cleanup_dhcp(networks)
            else:
                dhcp_agents.append(agent['id'])
                LOG.info('Active dhcp agents: %s' % agent['id'])
                if not hosted_networks and self.is_same_host(agent['host']):
                    self.cleanup_dhcp(None)

        agents = quantum.list_agents(agent_type=L3_AGENT)
        routers = {}
        for agent in agents['agents']:
            hosted_routers = quantum.list_routers_on_l3_agent(
                agent['id'])['routers']
            if not agent['alive']:
                LOG.info('L3 Agent %s down' % agent['id'])
                for router in hosted_routers:
                    routers[router['id']] = agent['id']
                if self.is_same_host(agent['host']):
                    self.cleanup_router(routers)
            else:
                l3_agents.append(agent['id'])
                LOG.info('Active l3 agents: %s' % agent['id'])
                if not hosted_routers and self.is_same_host(agent['host']):
                    self.cleanup_router(None)

        if not networks and not routers:
            LOG.info('No networks and routers hosted on failed agents.')
            return

        if len(dhcp_agents) == 0 and len(l3_agents) == 0:
            LOG.error('Unable to relocate resources, there are %s dhcp_agents '
                      'and %s l3_agents in this cluster' % (len(dhcp_agents),
                                                            len(l3_agents)))
            return

        if len(l3_agents) != 0:
            self.l3_agents_reschedule(l3_agents, routers, quantum)
            # new l3 node will not create a tunnel if don't restart ovs process
            self.restart_ovs_process()

        if len(dhcp_agents) != 0:
            self.dhcp_agents_reschedule(dhcp_agents, networks, quantum)

    def restart_ovs_process(selfs):
        try:
            cmd = ['sudo', 'service', 'openvswitch-switch', 'restart']
            output = subprocess.check_output(cmd)
        except Exception as e:
            pass

    def check_local_agents(self):
        services = ['openvswitch-switch', 'neutron-dhcp-agent',
                    'neutron-metadata-agent', 'neutron-vpn-agent']
        for s in services:
             status = ['sudo', 'service', s, 'status']
             restart = ['sudo', 'service', s, 'restart']
             ovs_agent_restart = ['sudo', 'service',
                                  'neutron-plugin-openvswitch-agent', 'restart']
             l3_restart = ['sudo', 'service', 'neutron-vpn-agent', 'restart']
             try:
                 output = subprocess.check_output(status)
             except Exception as e:
                 subprocess.check_output(restart)
                 if s == 'openvswitch-switch':
                     subprocess.check_output(ovs_agent_restart)
                 if s == 'neutron-metadata-agent':
                     subprocess.check_output(l3_restart)

    def run(self):
        while True:
            LOG.info('Monitor Neutron HA Agent Loop Start')
            self.reassign_agent_resources()
            self.check_local_agents()
            LOG.info('sleep %s' % cfg.CONF.check_interval)
            time.sleep(float(cfg.CONF.check_interval))


if __name__ == '__main__':
    opts = [
        cfg.StrOpt('check_interval',
                   default=15,
                   help='Check Neutron Agents interval.'),
    ]

    cfg.CONF.register_cli_opts(opts)
    cfg.CONF(project='monitor_neutron_agents', default_config_files=[])
    logging.setup('Neuron-HA-Monitor')
    monitor_daemon = MonitorNeutronAgentsDaemon()
    monitor_daemon.start()
