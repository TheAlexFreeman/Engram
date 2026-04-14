## [[ On Local Machine ]]
## ----------------------

# Set up an SSH Key Locally.
ssh-keygen -t ed25519 -a 112 -f ~/.ssh/id_ed25519_your_chosen_name -C "Your Chosen Comment"
chmod 600 ~/.ssh/id_ed25519_your_chosen_name
chmod 644 ~/.ssh/id_ed25519_your_chosen_name.pub

# Get `id_ed25519_your_chosen_name.pub` from Local Machine onto `/home/ubuntu`.
scp ~/.ssh/id_ed25519_your_chosen_name.pub ubuntu@remote_machine_ip:/home/ubuntu

# Will probably have to enter password at this step until the SSH Key is set up, etc.
ssh -l ubuntu remote_machine_ip

## -----------------------
## [[ On Remote Machine ]]
## -----------------------

# Get `vim`, `htop`, and any other useful packages installed.
cd ~
sudo apt-get update && sudo apt-get install vim htop curl unzip wget git jq -y

# If needed, install `snap`.
sudo apt update && sudo apt install snapd -y

# Install `task` (https://taskfile.dev/installation/#snap)
sudo snap install task --classic

# Change the default editor to `vim`.
sudo update-alternatives --config editor

### Editing step
sudo vim /etc/ssh/sshd_config

# * DevOps_Server_Setup_TODO: Replace 4802 everywhere relevant with the actual port.
# - Set Port to 4802 (4802 in this example will be the custom SSH port).
# - Decide on Keeping `PasswordAuthentication yes` and make changes if desired.
# - Decide on Keeping `PubkeyAuthentication yes` and make changes if desired.

### Editing step
# ! Important: First do this below. Don't vim the file until this has been done.
sudo systemctl edit ssh.socket
# ```
# [Socket]
# ListenStream=
# ListenStream=0.0.0.0:4802
# ListenStream=[::]:4802
# ```
#
# Important NOTE: In some cases, Both IPv4 (0.0.0.0:4802) and IPv6 ([::]:4802) must be
# specified. Without explicit IPv4 binding, SSH will only listen on IPv6, causing
# "Connection refused" errors for IPv4 connections. The empty ListenStream= line
# disables the default port 22 listener.
#
# Can now `vim` to edit the file if you want.
sudo vim /etc/systemd/system/ssh.socket.d/override.conf

cd ~
cat ./id_ed25519_your_chosen_name.pub >> ~/.ssh/authorized_keys
rm ./id_ed25519_your_chosen_name.pub
sudo systemctl reload ssh.service

# May only need a subset of these commands, but this covers a lot of bases.
sudo systemctl restart ssh.socket
sudo systemctl daemon-reload
sudo systemctl restart ssh.socket
sudo systemctl restart ssh
sudo service ssh restart
sudo systemctl reload ssh.service
sudo systemctl daemon-reload

# Important: Make sure directory permissions are permissive enough for SSH, and make
# sure SSH is actually enabled (now and on boot).
sudo chmod 755 /home/ubuntu
sudo systemctl enable ssh
sudo systemctl enable ssh.socket

# Set up the Magic File
cd ~
# See https://stackoverflow.com/a/5688625 for more context.
sudo fallocate -l 8G magic_storage_image.img

## ----------------------
## [[ On Local Machine ]]
## ----------------------

### Editing step
vim ~/.ssh/config
# You'll want to add the following (or something similar) to the file:
# ```
# Host remote_machine_ip
#   HostName remote_machine_ip
#   User ubuntu
#   Port 4802
#   IdentityFile ~/.ssh/id_ed25519_your_chosen_name
# ```

### Check step
ssh remote_machine_ip
# ^ This should work as intended without needing to enter a password.

## -----------------------
## [[ On Remote Machine ]]
## -----------------------

# `ufw`
# ========================================
# Set up `ufw`.
sudo apt update && sudo apt install ufw -y
sudo ufw enable

# Set up `ufw` firewall rules, rate limiting, and related.
sudo ufw status verbose
sudo ufw limit log 4802/tcp comment 'Rate limit for port 4802 (SSH)'
# * DevOps_Server_Setup_TODO: Replace 1802 everywhere relevant with the actual port.
sudo ufw allow 1802/tcp
# NOTE: Limiting this breaks PowerBI, so you probably don't want to limit this if you're
# using PowerBI or another heavy BI tool, etc.
# sudo ufw limit log 1802/tcp comment 'Rate limit for port 1802 (PostgreSQL)'
sudo ufw limit log ssh comment 'Rate limit for the OpenSSH server'
sudo ufw deny 22/tcp comment 'Disallow SSH on port 22'
# Allow Docker services to connect to PostgreSQL.
sudo ufw allow from 172.16.0.0/12 to any port 1802 proto tcp comment 'Docker to PostgreSQL'
sudo ufw allow from 192.168.0.0/16 to any port 1802 proto tcp comment 'Docker to PostgreSQL'
sudo ufw allow from 10.0.0.0/8 to any port 1802 proto tcp comment 'Docker to PostgreSQL'
sudo ufw status verbose

# Docker
# ========================================
for pkg in docker.io docker-doc docker-compose docker-compose-v2 podman-docker containerd runc; do sudo apt-get remove $pkg; done

# Add Docker's official GPG key:
sudo apt-get update
sudo apt-get install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
# Add the repository to Apt sources:
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update

sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

sudo systemctl status docker
sudo systemctl start docker
sudo systemctl enable docker

sudo docker run hello-world

sudo groupadd docker
sudo usermod -aG docker $USER
newgrp docker
docker run hello-world

sudo systemctl enable docker.service
sudo systemctl enable containerd.service

# NOTE: This is no an actual function/command, just a placeholder to say that you set
# the `daemon.json` file appropriately to `json-file`, etc.
update_docker_daemon(...)

# UV
# ========================================
curl -LsSf https://astral.sh/uv/install.sh | bash

# Bun
# ========================================
curl -fsSL https://bun.sh/install | bash

# AWS CLI
# ========================================
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# PostgreSQL
# ========================================
sudo apt update
sudo apt install -y postgresql-common
sudo /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh
sudo apt update

sudo apt install postgresql-18

sudo mkdir -p /etc/postgresql/18/main/conf.d
sudo chown -R postgres:postgres /etc/postgresql/18/

sudo systemctl start postgresql
sudo systemctl enable postgresql

psql --version

# NOTE: This is no an actual function/command, just a placeholder to say that you update
# the PostgreSQL configuration file(s), set listening address(es), etc.
update_postgresql_configuration(...)

# NOTE: This is no an actual function/command, just a placeholder to say that you run
# the `setup_postgres_db.sh` script(s)/command(s), etc. with appropriate info.
run_setup_postgres_db_steps(...)

# Codebase(s) and Related
# ========================================
cd ~/.ssh
ssh-keygen
# NOTE: This is no an actual function/command, just a placeholder to say that you setup
# the GitHub Deploy Key(s), etc.
setup_github_deploy_keys(...)

cd ~
mkdir -p proj
cd proj
git clone git@github.com:elyon-tech/better-base.git

cd ~

sudo cp /home/ubuntu/proj/better-base/scripts/prod/server_files/etc/docker/daemon.json /etc/docker/daemon.json
sudo chown root:root /etc/docker/daemon.json
sudo systemctl restart docker.service
sudo systemctl restart containerd.service

sudo cp -r /home/ubuntu/proj/better-base/scripts/prod/server_files/etc/postgresql/18/main/conf.d/* /etc/postgresql/18/main/conf.d/
sudo cp /home/ubuntu/proj/better-base/scripts/prod/server_files/etc/postgresql/18/main/pg_hba.conf /etc/postgresql/18/main/pg_hba.conf
sudo chown -R postgres:postgres /etc/postgresql/18/
sudo systemctl restart postgresql

# NOTE: This is no an actual function/command, just a placeholder to say that you should
# set up the R2 buckets and credentials. Which, at the time of writing, may entail
# running `setup_cloudflare_buckets.sh` (after making necessary changes/setting env
# vars) and then automatedly or manually grabbing the necessary credentials for below
# steps.
set_r2_buckets_and_credentials(...)

mkdir -p /home/ubuntu/.aws
cp /home/ubuntu/proj/better-base/scripts/prod/\$user/.aws/config /home/ubuntu/.aws/config
cp /home/ubuntu/proj/better-base/scripts/prod/\$user/.aws/credentials /home/ubuntu/.aws/credentials
# NOTE: This is no an actual function/command, just a placeholder to say that you should
# update the Cloudflare R2 S3-compatible credentials.
update_cloudflare_r2_s3_compatible_credentials(...)

mkdir -p /home/ubuntu/backups/db
mkdir -p /home/ubuntu/backups/staged/db
mkdir -p /home/ubuntu/backups/fixtures/

sudo cp /home/ubuntu/proj/better-base/scripts/prod/server_files/etc/systemd/system/backup-db.service /etc/systemd/system/backup-db.service
sudo cp /home/ubuntu/proj/better-base/scripts/prod/server_files/etc/systemd/system/backup-db.timer /etc/systemd/system/backup-db.timer
sudo systemctl enable backup-db.timer
sudo systemctl start backup-db.timer
sudo systemctl daemon-reload

cd /home/ubuntu/proj/better-base

# NOTE: This is no an actual function/command, just a placeholder to say that you should
# populate/copy the necessary codebase environment variables, files, secrets, etc.
populate_codebase_environment_variables_and_files_and_secrets(...)

task pbuild
task pm
task pup

cd ~

sudo systemctl daemon-reload

# Certbot
# ========================================
mkdir -p /home/ubuntu/.secrets/certbot
cp /home/ubuntu/proj/better-base/scripts/prod/\$user/.secrets/certbot/cloudflare.ini /home/ubuntu/.secrets/certbot/cloudflare.ini

# NOTE: This is no an actual function/command, just a placeholder to say that you should
# add the necessary Cloudflare info/secrets to the
# `/home/ubuntu/.secrets/certbot/cloudflare.ini` file if you're exposing the Postgres
# port outside of the box.
add_cloudflare_info_to_certbot_ini(...)

# NOTE: This is no an actual function/command, just a placeholder to say that you should
# run the `certbot_steps.sh` script if you're exposing the Postgres port outside of the
# box.
run_certbot_steps(...)

# Misc/Useful
# ========================================
# Append aliases to `~/.bashrc` only if the below marker is not present.
if ! grep -q "~~ Misc/Useful Aliases ~~" ~/.bashrc 2>/dev/null; then
    cat >> ~/.bashrc << 'EOF'

# ~~ Misc/Useful Aliases ~~
# Alias various `git` commands.
alias g='git'
alias gc='git checkout'
alias gd='git diff'
alias gp='git pull'
alias gs='git status'
# Alias the `task` command (for Taskfiles) to `t`.
alias t='task'
# Alias the `bun` command (for Bun) to `b`.
alias b='bun'
# Alias the `ur` command to `uv run`.
alias ur='uv run'
# Alias the `ux` command to `uvx run`.
alias ux='uvx run'
# Alias the `docker compose` command (for Docker Compose) to `dc` and default to `-f
# dc.prod.yml`.
alias dc='docker compose -f dc.prod.yml'
# Alias the `docker compose run --rm` command (for Docker Compose) to `dcr` and default
# to `-f dc.prod.yml` and the `django` service.
alias dcr='docker compose -f dc.prod.yml run --rm django'
# Alias the `ds` command to run a Django shell.
alias ds='docker compose -f dc.prod.yml run --rm django python manage.py shell_plus'
# Alias the `dm` command to run Django migrations.
alias dm='docker compose -f dc.prod.yml run --rm django python manage.py migrate'
# Alias the `p` command to go to the main codebase (project) directory.
alias p='cd /home/ubuntu/proj/better-base'
EOF
fi
