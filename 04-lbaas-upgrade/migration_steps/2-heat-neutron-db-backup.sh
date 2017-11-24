#!/bin/bash

backup_dir=backup-$(hostname)
mkdir $backup_dir

sudo mysqldump --no-create-info --no-create-db --extended-insert --single-transaction --complete-insert --insert-ignore \
        neutron members poolmonitorassociations poolstatisticss pools poolloadbalanceragentbindings vips healthmonitors | gzip > $backup_dir/neutron-lbaas-v1-pre-upgrade-backup.sql.gz

sudo mysqldump --add-drop-database heat | gzip > $backup_dir/heat.sql.gz

