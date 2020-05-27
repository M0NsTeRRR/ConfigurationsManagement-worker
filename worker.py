# ----------------------------------------------------------------------------
# Copyright © Ortega Ludovic, 2020
#
# Contributeur(s):
#     * Ortega Ludovic - mastership@hotmail.fr
#
# Ce logiciel, ConfigurationsManagement-worker est un outil qui permet de
# sauvegarder/restorer des serveurs/services.
#
# Ce logiciel est régi par la licence CeCILL soumise au droit français et
# respectant les principes de diffusion des logiciels libres. Vous pouvez
# utiliser, modifier et/ou redistribuer ce programme sous les conditions
# de la licence CeCILL telle que diffusée par le CEA, le CNRS et l'INRIA
# sur le site "http://www.cecill.info".
#
# En contrepartie de l'accessibilité au code source et des droits de copie,
# de modification et de redistribution accordés par cette licence, il n'est
# offert aux utilisateurs qu'une garantie limitée.  Pour les mêmes raisons,
# seule une responsabilité restreinte pèse sur l'auteur du programme,  le
# titulaire des droits patrimoniaux et les concédants successifs.
#
# A cet égard  l'attention de l'utilisateur est attirée sur les risques
# associés au chargement,  à l'utilisation,  à la modification et/ou au
# développement et à la reproduction du logiciel par l'utilisateur étant
# donné sa spécificité de logiciel libre, qui peut le rendre complexe à
# manipuler et qui le réserve donc à des développeurs et des professionnels
# avertis possédant  des  connaissances  informatiques approfondies.  Les
# utilisateurs sont donc invités à charger  et  tester  l'adéquation  du
# logiciel à leurs besoins dans des conditions permettant d'assurer la
# sécurité de leurs systèmes et ou de leurs données et, plus généralement,
# à l'utiliser et l'exploiter dans les mêmes conditions de sécurité.
#
# Le fait que vous puissiez accéder à cet en-tête signifie que vous avez
# pris connaissance de la licence CeCILL, et que vous en avez accepté les
# termes.
# ----------------------------------------------------------------------------

import os
import logging
import json
from datetime import datetime, timezone
from sys import exit as sys_exit

import yaml
import pika
import requests

from ansible.errors import AnsibleError
from ansible.module_utils._text import to_bytes
from ansible.module_utils.common.collections import ImmutableDict
from ansible.parsing.dataloader import DataLoader
from ansible.parsing.vault import VaultSecret
from ansible.vars.manager import VariableManager
from ansible.inventory.manager import InventoryManager
from ansible.plugins.callback import CallbackBase
from ansible import context
from ansible.executor.playbook_executor import PlaybookExecutor


logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s', level=logging.INFO, datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)


CONFIG = None
try:
    with open("config.yml", "r") as f:
        CONFIG = yaml.safe_load(f)
except Exception as e:
    logger.error("Can't load config.yml")
    sys_exit(1)

ROOT_DIR = os.path.dirname(os.path.realpath(__file__))
try:
    CONFIG['ANSIBLE']['VAULT_SECRET'] = os.environ.get('ANSIBLE_VAULT_SECRET') or CONFIG['ANSIBLE'].get('VAULT_SECRET', '')
    CONFIG['RABBITMQ']['HOST'] = os.environ.get('RABBITMQ_HOST') or CONFIG['RABBITMQ'].get('HOST', 'localhost')
    CONFIG['RABBITMQ']['PORT'] = int(os.environ.get('RABBITMQ_PORT') or CONFIG['RABBITMQ'].get('PORT', 5672))
    CONFIG['RABBITMQ']['QUEUE'] = os.environ.get('RABBITMQ_QUEUE') or CONFIG['RABBITMQ'].get('QUEUE', 'tasks')
    CONFIG['RABBITMQ']['LOGIN'] = os.environ.get('RABBITMQ_LOGIN') or CONFIG['RABBITMQ'].get('LOGIN', '')
    CONFIG['RABBITMQ']['PASSWORD'] = os.environ.get('RABBITMQ_PASSWORD') or CONFIG['RABBITMQ'].get('PASSWORD', '')
except Exception as e:
    logger.error("config.yml is not filled properly")
    logger.error(e)
    sys_exit(1)


class TaskFailure(Exception):
   pass


class AnsibleCallback(CallbackBase):
    def __init__(self, display=None, options=None):
        super().__init__(display, options)
        self.custom_rc = 1
        self.custom_error = ''

    def v2_runner_on_ok(self, result, **kwargs):
        pass

    def v2_runner_on_failed(self, result, ignore_errors=False):
        self.custom_rc = -1
        if 'stderr' in result._result:
            self.custom_error = result._result["stderr"]
        elif 'msg' in result._result:
            self.custom_error = result._result["msg"]
        elif 'message' in result._result:
            self.custom_error = result._result["message"]
        else:
            self.custom_error = "No traceback"


def pika_callback(ch, method, _, body):
    task = json.loads(body)

    try:
        logger.info(f"Task received id={task['id']}")
        requests.put(f"{CONFIG['CONFIGURATIONSMANAGEMENT']['BASE_URL']}/tasks/task/{task['id']}", {'worker_token': task['worker_token'], 'state': 2})

        playbook_path = f"{ROOT_DIR}/modules/{task['module']}/{task['action']}.yml"

        loader = DataLoader()
        loader.set_vault_secrets([('default',VaultSecret(_bytes=to_bytes(CONFIG['ANSIBLE']['VAULT_SECRET'])))])
        context.CLIARGS = ImmutableDict(
            syntax=False,
            verbosity=False,
            start_at_task=None,
            extra_vars={
                '@secrets.yml',
                f'gitea_token={task["gitea"]["token"]}',
                f'gitea_url={task["gitea"]["url"]}',
                f'gitea_owner={task["gitea"]["owner"]}',
                f'gitea_repository={task["gitea"]["repository"]}',
                f'path={task["path"]}',
                f'hostname={task["hostname"]}'
            }
        )
        inventory = InventoryManager(loader=loader, sources=f'localhost,{task["hostname"]}')
        variable_manager = VariableManager(loader=loader, inventory=inventory)
        results_callback = AnsibleCallback()
        pbex = PlaybookExecutor(playbooks=[playbook_path], inventory=inventory, variable_manager=variable_manager, loader=loader, passwords={})
        pbex._tqm._stdout_callback = results_callback
        r = pbex.run()
        if results_callback.custom_rc == -1:
            logger.error("Task failed")
            logger.error(f"Traceback => {results_callback.custom_error}")
            requests.put(f"{CONFIG['CONFIGURATIONSMANAGEMENT']['BASE_URL']}/tasks/task/{task['id']}", {'worker_token': task['worker_token'], 'state': 3, 'error': 1, 'message': f"Ansible traceback : {results_callback.custom_error}", 'end_date': datetime.now(timezone.utc)})
        else:
            requests.put(f"{CONFIG['CONFIGURATIONSMANAGEMENT']['BASE_URL']}/tasks/task/{task['id']}", {'worker_token': task['worker_token'], 'state': 3, 'end_date': datetime.now(timezone.utc)})
            logger.info("Task successfull")
    except AnsibleError as e:
        requests.put(f"{CONFIG['CONFIGURATIONSMANAGEMENT']['BASE_URL']}/tasks/task/{task['id']}", {'worker_token': task['worker_token'], 'state': 3, 'error': 1, 'message': f"Ansible traceback : {e}", 'end_date': datetime.now(timezone.utc)})
        logger.error(f"{e}")
    except requests.exceptions.RequestException as e:
        logger.error(f"{e}")
    except Exception as e:
        requests.put(f"{CONFIG['CONFIGURATIONSMANAGEMENT']['BASE_URL']}/tasks/task/{task['id']}", {'worker_token': task['worker_token'], 'state': 3, 'error': 1, 'message': 'An exception occurred during task execution.', 'end_date': datetime.now(timezone.utc)})
        logger.error(f"{e}")
    ch.basic_ack(delivery_tag=method.delivery_tag)

try:
    credentials = pika.credentials.PlainCredentials(CONFIG['RABBITMQ']['LOGIN'], CONFIG['RABBITMQ']['PASSWORD'])
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=CONFIG['RABBITMQ']['HOST'], port=CONFIG['RABBITMQ']['PORT'], credentials=credentials))
    channel = connection.channel()
    channel.queue_declare(queue=CONFIG['RABBITMQ']['QUEUE'], durable=True)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=CONFIG['RABBITMQ']['QUEUE'], on_message_callback=pika_callback)
    channel.start_consuming()
except Exception as e:
    logger.error(f"{e}")

