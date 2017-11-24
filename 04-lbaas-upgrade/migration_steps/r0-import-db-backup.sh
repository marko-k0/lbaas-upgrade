#!/bin/bash

backup_dir=backup-$(hostname)
cd $backup_dir

test -f heat.sql.gz && gunzip heat.sql.gz
mysql heat < heat.sql
cd -

