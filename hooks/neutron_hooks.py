#!/usr/bin/env python3

from base64 import b64decode

from charmhelpers.core.hookenv import (
    log, ERROR, WARNING,
    config,
    relation_get,
    relation_set,
    relation_ids,
    Hooks,
    UnregisteredHookError,
    status_set,
)
from charmhelpers.core.host import service_restart
from charmhelpers.core.unitdata import kv
from charmhelpers.fetch import (
    apt_update,
    apt_install,
    filter_installed_packages,
    apt_purge,
)
from charmhelpers.core.host import (
    is_container,
    lsb_release,
)
from charmhelpers.contrib.hahelpers.cluster import(
    get_hacluster_config,
)
from charmhelpers.contrib.hahelpers.apache import(
    install_ca_cert
)
from charmhelpers.contrib.openstack.utils import (
    configure_installation_source,
    openstack_upgrade_available,
    pausable_restart_on_change as restart_on_change,
    is_unit_paused_set,
    series_upgrade_prepare,
    series_upgrade_complete,
)
from charmhelpers.payload.execd import execd_preinstall
from charmhelpers.core.sysctl import create as create_sysctl

from charmhelpers.contrib.charmsupport import nrpe
from charmhelpers.contrib.hardening.harden import harden

import sys
from neutron_utils import (
    L3HA_PACKAGES,
    register_configs,
    restart_map,
    services,
    do_openstack_upgrade,
    get_packages,
    get_early_packages,
    valid_plugin,
    configure_ovs,
    stop_services,
    cache_env_data,
    update_legacy_ha_files,
    remove_legacy_ha_files,
    install_legacy_ha_files,
    cleanup_ovs_netns,
    stop_neutron_ha_monitor_daemon,
    use_l3ha,
    NEUTRON_COMMON,
    assess_status,
    install_systemd_override,
    configure_apparmor,
    pause_unit_helper,
    resume_unit_helper,
    remove_legacy_nova_metadata,
    disable_nova_metadata,
    remove_old_packages,
)

hooks = Hooks()
CONFIGS = register_configs()


@hooks.hook('install')
@harden()
def install():
    status_set('maintenance', 'Executing pre-install')
    execd_preinstall()
    src = config('openstack-origin')
    if (lsb_release()['DISTRIB_CODENAME'] == 'precise' and
            src == 'distro'):
        src = 'cloud:precise-icehouse'
    configure_installation_source(src)
    status_set('maintenance', 'Installing apt packages')
    apt_update(fatal=True)
    apt_install('python-six', fatal=True)  # Force upgrade
    if valid_plugin():
        apt_install(filter_installed_packages(get_early_packages()),
                    fatal=True)
        apt_install(filter_installed_packages(get_packages()),
                    fatal=True)
    else:
        message = 'Please provide a valid plugin config'
        log(message, level=ERROR)
        status_set('blocked', message)
        sys.exit(1)

    # Legacy HA for Icehouse
    update_legacy_ha_files()

    # Install systemd overrides to remove service startup race between
    # n-gateway and n-cloud-controller services.
    install_systemd_override()


@hooks.hook('config-changed')
@restart_on_change(restart_map())
@harden()
def config_changed():
    global CONFIGS
    if not config('action-managed-upgrade'):
        if openstack_upgrade_available(NEUTRON_COMMON):
            status_set('maintenance', 'Running openstack upgrade')
            do_openstack_upgrade(CONFIGS)

    update_nrpe_config()

    sysctl_settings = config('sysctl')
    if sysctl_settings:
        if is_container():
            log("Cannot create sysctls inside of a container", level=WARNING)
        else:
            create_sysctl(sysctl_settings,
                          '/etc/sysctl.d/50-quantum-gateway.conf')

    # Re-run joined hooks as config might have changed
    for r_id in relation_ids('amqp'):
        amqp_joined(relation_id=r_id)
    for r_id in relation_ids('amqp-nova'):
        amqp_nova_joined(relation_id=r_id)
    if valid_plugin():
        CONFIGS.write_all()
        configure_ovs()
        configure_apparmor()
    else:
        message = 'Please provide a valid plugin config'
        log(message, level=ERROR)
        status_set('blocked', message)
        sys.exit(1)
    if config('plugin') == 'n1kv':
        if config('enable-l3-agent'):
            status_set('maintenance', 'Installing apt packages')
            apt_install(filter_installed_packages('neutron-l3-agent'))
        else:
            apt_purge('neutron-l3-agent')

    # Setup legacy ha configurations
    update_legacy_ha_files()
    # Disable nova metadata if possible,
    if disable_nova_metadata():
        remove_legacy_nova_metadata()


@hooks.hook('upgrade-charm')
@harden()
def upgrade_charm():
    install()
    packages_removed = remove_old_packages()
    if packages_removed and not is_unit_paused_set():
        log("Package purge detected, restarting services", "INFO")
        for s in services():
            service_restart(s)
    config_changed()
    update_legacy_ha_files(force=True)

    # Install systemd overrides to remove service startup race between
    # n-gateway and n-cloud-controller services.
    install_systemd_override()


@hooks.hook('amqp-nova-relation-joined')
def amqp_nova_joined(relation_id=None):
    relation_set(relation_id=relation_id,
                 username=config('nova-rabbit-user'),
                 vhost=config('nova-rabbit-vhost'))


@hooks.hook('amqp-relation-joined')
def amqp_joined(relation_id=None):
    relation_set(relation_id=relation_id,
                 username=config('rabbit-user'),
                 vhost=config('rabbit-vhost'))


@hooks.hook('amqp-nova-relation-departed')
@hooks.hook('amqp-nova-relation-changed')
@restart_on_change(restart_map())
def amqp_nova_changed():
    if 'amqp-nova' not in CONFIGS.complete_contexts():
        log('amqp relation incomplete. Peer not ready?')
        return
    CONFIGS.write_all()


@hooks.hook('amqp-relation-departed')
@restart_on_change(restart_map())
def amqp_departed():
    if 'amqp' not in CONFIGS.complete_contexts():
        log('amqp relation incomplete. Peer not ready?')
        return
    CONFIGS.write_all()


@hooks.hook('amqp-relation-changed',
            'cluster-relation-changed',
            'cluster-relation-joined')
@restart_on_change(restart_map())
def amqp_changed():
    CONFIGS.write_all()


@hooks.hook('neutron-plugin-api-relation-changed')
@restart_on_change(restart_map())
def neutron_plugin_api_changed():
    if use_l3ha():
        apt_update()
        apt_install(L3HA_PACKAGES, fatal=True)
    CONFIGS.write_all()


@hooks.hook('quantum-network-service-relation-changed')
@restart_on_change(restart_map())
def nm_changed():
    CONFIGS.write_all()
    if relation_get('ca_cert'):
        ca_crt = b64decode(relation_get('ca_cert'))
        install_ca_cert(ca_crt)

    if config('ha-legacy-mode'):
        cache_env_data()

    # Disable nova metadata if possible,
    if disable_nova_metadata():
        remove_legacy_nova_metadata()
    else:
        # NOTE: nova-api-metadata needs to be restarted
        #       once the nova-conductor is up and running
        #       on the nova-cc units.
        restart_nonce = relation_get('restart_trigger')
        if restart_nonce is not None:
            db = kv()
            previous_nonce = db.get('restart_nonce')
            if previous_nonce != restart_nonce:
                if not is_unit_paused_set():
                    service_restart('nova-api-metadata')
                db.set('restart_nonce', restart_nonce)
                db.flush()


@hooks.hook("cluster-relation-departed")
@restart_on_change(restart_map())
def cluster_departed():
    if config('plugin') in ['nvp', 'nsx']:
        log('Unable to re-assign agent resources for'
            ' failed nodes with nvp|nsx',
            level=WARNING)
        return
    if config('plugin') == 'n1kv':
        log('Unable to re-assign agent resources for failed nodes with n1kv',
            level=WARNING)
        return


@hooks.hook('cluster-relation-broken')
@hooks.hook('stop')
def stop():
    stop_services()
    if config('ha-legacy-mode'):
        # Cleanup ovs and netns for destroyed units.
        cleanup_ovs_netns()


@hooks.hook('nrpe-external-master-relation-joined',
            'nrpe-external-master-relation-changed')
def update_nrpe_config():
    # python-dbus is used by check_upstart_job
    apt_install('python-dbus')
    hostname = nrpe.get_nagios_hostname()
    current_unit = nrpe.get_nagios_unit_name()
    nrpe_setup = nrpe.NRPE(hostname=hostname)
    nrpe.add_init_service_checks(nrpe_setup, services(), current_unit)

    cronpath = '/etc/cron.d/nagios-netns-check'
    cron_template = ('*/5 * * * * root '
                     '/usr/local/lib/nagios/plugins/check_netns.sh '
                     '> /var/lib/nagios/netns-check.txt\n'
                     )
    f = open(cronpath, 'w')
    f.write(cron_template)
    f.close()
    nrpe_setup.add_check(
        shortname="netns",
        description='Network Namespace check {%s}' % current_unit,
        check_cmd='check_status_file.py -f /var/lib/nagios/netns-check.txt'
    )
    nrpe_setup.write()


@hooks.hook('ha-relation-joined')
@hooks.hook('ha-relation-changed')
def ha_relation_joined():
    if config('ha-legacy-mode'):
        log('ha-relation-changed update_legacy_ha_files')
        install_legacy_ha_files()
        cache_env_data()
        cluster_config = get_hacluster_config(exclude_keys=['vip'])
        resources = {
            'res_monitor': 'ocf:canonical:NeutronAgentMon',
        }
        resource_params = {
            'res_monitor': 'op monitor interval="60s"',
        }
        clones = {
            'cl_monitor': 'res_monitor meta interleave="true"',
        }

        relation_set(corosync_bindiface=cluster_config['ha-bindiface'],
                     corosync_mcastport=cluster_config['ha-mcastport'],
                     resources=resources,
                     resource_params=resource_params,
                     clones=clones)


@hooks.hook('ha-relation-departed')
def ha_relation_destroyed():
    # If e.g. we want to upgrade to Juno and use native Neutron HA support then
    # we need to un-corosync-cluster to enable the transition.
    if config('ha-legacy-mode'):
        stop_neutron_ha_monitor_daemon()
        remove_legacy_ha_files()


@hooks.hook('update-status')
@harden()
def update_status():
    log('Updating status.')


@hooks.hook('pre-series-upgrade')
def pre_series_upgrade():
    log("Running prepare series upgrade hook", "INFO")
    series_upgrade_prepare(
        pause_unit_helper, CONFIGS)


@hooks.hook('post-series-upgrade')
def post_series_upgrade():
    log("Running complete series upgrade hook", "INFO")
    series_upgrade_complete(
        resume_unit_helper, CONFIGS)


if __name__ == '__main__':
    try:
        hooks.execute(sys.argv)
    except UnregisteredHookError as e:
        log('Unknown hook {} - skipping.'.format(e))
    assess_status(CONFIGS)
