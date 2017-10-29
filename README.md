# Neutron LBaaS v1 to v2 Upgrade POC

## Packstack

```bash
sudo -i
cd lbaas-upgrade/00-packstack-setup
./packstack.sh
```

## Horizon

Horizon Newton is needed for LBaaS V2 UI.

```bash
cd 01-horizon-upgrade
./horizon-newton.sh
```

## Populate Heat/LBaaS Environment

### General POC

General POC data (TCP/HTTP/HTTPS load balancers).

```bash
cd 02-os-data-populate
./os-init.sh
./os-create-stacks.sh
```

## Heat Upgrade

Heat Newton is needed for LBaaS V2 resources (available with Mitaka realease but let's do Newton).

```
cd 03-heat-upgrade
./heat-newton.sh
```

## LBaaS Upgrade

The core part!

```
cd 04-lbaas-upgrades
./lbaas-migration.sh
```

## Test Cases

Delete/update heat stacks.

