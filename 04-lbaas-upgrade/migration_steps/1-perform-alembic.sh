#!/bin/bash

sudo cp ../4aff599b9845_lbaas_v1_to_v2_migration.py /usr/lib/python2.7/site-packages/neutron_lbaas/db/migration/alembic_migrations/versions/liberty/expand/
sudo sed -i 's/3345facd0452/4aff599b9845/g' /usr/lib/python2.7/site-packages/neutron_lbaas/db/migration/alembic_migrations/versions/HEADS

sudo neutron-db-manage --subproject neutron-lbaas upgrade head

sudo rm /usr/lib/python2.7/site-packages/neutron_lbaas/db/migration/alembic_migrations/versions/liberty/expand/4aff599b9845_lbaas_v1_to_v2_migration.py
sudo sed -i 's/4aff599b9845/3345facd0452/g' /usr/lib/python2.7/site-packages/neutron_lbaas/db/migration/alembic_migrations/versions/HEADS
sudo mysql neutron -e "update alembic_version_lbaas set version_num = '3345facd0452' where version_num = '4aff599b9845'"
