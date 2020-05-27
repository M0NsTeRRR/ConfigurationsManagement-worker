![Python version](https://img.shields.io/badge/python-3.6%20%7C%203.7%20%7C%203.8-blue)
![Ansible version](https://img.shields.io/badge/ansible-2.9-blue)
[![Licence](https://img.shields.io/badge/license-CeCILL%20V2.1-green)](https://github.com/M0NsTeRRR/ConfigurationsManagement-worker/blob/master/LICENSE)


ConfigurationsManagement is a website that helps you to backup/restore devices/services. An API is available to automate
backup/restore. ConfigurationsManagement send task to execute to ConfigurationsManagement-worker through RabbitMQ Work queues. Files are saved
in a Gitea server. Backup/Restore script are Ansible Playbooks.

[ConfigurationsManagement](https://github.com/M0NsTeRRR/ConfigurationsManagement)

# Requirements
- Python > 3.6
- Pip
- OS: Linux only
- Ansible > 2.9

# Install

**Be sure to use the same version of the code as the version of the docs
you're reading.**

    # clone the repository
    $ git clone https://github.com/M0NsTeRRR/ConfigurationsManagement-worker
    $ cd ConfigurationsManagement-worker
    # checkout the correct version
    $ git tag # shows the tagged versions
    $ git checkout <latest-tag-found-above>

## Install dependencies

    $ pip install -e .

# Configuration
Create the secrets file `secrets.yml` based on `secrets.example` after that encrypt the file with ansible-vault
Create the config file `config.yml` or fill environment variable based on `config.example`
Example : To configure host of rabbitmq it will be RABBITMQ_HOST

# Run
$ python main.py

# Add a module
Create a folder in modules folder under this folder create two playbooks, save.yml and restore.yml.
In the save playbooks include at end gitea_upload.yml, it's a wrapper to upload a file in your repository.
In the restore playbooks include at first gitea_download.yml, it's a wrapper to download a file from your repository.
File will be uploaded/downloaded on gitea to local machine in /tmp/<value of path variable>

# Supported devices/services

## Pfsense, requirement : [pfsense_fauxapi](https://github.com/ndejong/pfsense_fauxapi)
Will save the configuration in a json

## Powerdns
Will save the configuration in a zip archive who contains one file per zone

## Asterisk
Will save :
    - /etc/asterisk/extensions.conf
    - /etc/asterisk/features.conf
    - /etc/asterisk/pjsip.conf
    - /etc/asterisk/voicemail.conf
in a zip archive

# Licence

The code is under CeCILL license.

You can find all details here: https://cecill.info/licences/Licence_CeCILL_V2.1-en.html

# Credits

Copyright © Ludovic Ortega, 2019

Contributor(s):

-Ortega Ludovic - mastership@hotmail.fr