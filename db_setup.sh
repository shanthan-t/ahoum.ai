#!/bin/bash
sudo -u postgres psql -c "CREATE DATABASE ahoum;"
sudo -u postgres psql -c "ALTER USER postgres WITH PASSWORD 'postgres';"
# On Fedora, we might need to change ident to md5 for localhost TCP connections
sudo sed -i 's/ident/md5/g' /var/lib/pgsql/data/pg_hba.conf
sudo systemctl restart postgresql
