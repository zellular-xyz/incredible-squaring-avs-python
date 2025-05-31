import os
import logging
import json
import time
import threading
import requests
import yaml
from web3 import Web3
import eth_abi
from eth_account import Account
from flask import Flask, request
from eigensdk.chainio.clients.builder import BuildAllConfig, build_all
from eigensdk.chainio.utils import nums_to_bytes
from eigensdk.crypto.bls.attestation import Signature, G1Point, G2Point, g1_to_tupple, g2_to_tupple, new_zero_g1_point, new_zero_g2_point

THRESHOLD_PERCENT = 70

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Aggregator:
    def __init__(self, config):
        self.config = config
        self.web3 = Web3(Web3.HTTPProvider(self.config["eth_rpc_url"]))
        self.__load_ecdsa_key()
        self.__load_clients()
        self.__load_task_manager()
        self.tasks = {}
        self.responses = {}
        self.app = Flask(__name__)
        self.app.add_url_rule('/signature', 'signature', self.submit_signature, methods=['POST'])
        self.subgraph_url = "http://localhost:8000/subgraphs/name/avs-subgraph"

    def __verify_signature(self, data, operators):
        if data['operator_id'] not in operators:
            raise ValueError("Operator is not registered")

        encoded = eth_abi.encode(["uint32", "uint256"], [data["task_index"], data["number_squared"]])
        task_response_digest = Web3.keccak(encoded)

        pub_key_g2 = operators[data["operator_id"]]["public_key_g2"]
        signature = Signature(data['signature']['X'], data['signature']['Y'])
        verified = signature.verify(pub_key_g2, task_response_digest)
        if not verified:
            raise ValueError("Incorrect signature error")

    def submit_signature(self):
        data = request.get_json()
        operators = self.__operators_info(data['block_number'])
        self.__verify_signature(data, operators)
        task_index = data["task_index"]
        operator_id = data["operator_id"]
        if task_index not in self.responses:
            self.responses[task_index] = {}
        if operator_id in self.responses[task_index]:
            raise ValueError("Operator signature has already been processed")

        self.responses[task_index][operator_id] = data
        signer_operator_ids = [operator_id for operator_id in self.responses[task_index] if self.responses[task_index][operator_id]["number_squared"] == data["number_squared"]]

        signed_stake = sum(operators[operator_id]["stake"] for operator_id in signer_operator_ids)
        total_stake = sum(operators[operator_id]["stake"] for operator_id in operators)
        if total_stake > 0 and signed_stake / total_stake < THRESHOLD_PERCENT:
            return "true", 200

        signatures = [self.responses[task_index][operator_id]["signature"] for operator_id in signer_operator_ids]
        non_signers_pubkeys_g1 = [operators[operator_id]["public_key_g1"] for operator_id in operators if operator_id not in signer_operator_ids]
        quorum_apks_g1 = sum([operators[operator_id]["public_key_g1"] for operator_id in operators], new_zero_g1_point())
        signers_apk_g2 = sum([operators[operator_id]["public_key_g2"] for operator_id in operators if operator_id in signer_operator_ids], new_zero_g2_point())
        signers_agg_sig_g1 = sum([Signature(signature['X'], signature['Y']) for signature in signatures], new_zero_g1_point())

        indices = self.clients.avs_registry_reader.get_check_signatures_indices(
            data["block_number"],
            [0],
            [int(operator_id, 16) for operator_id in operators if operator_id not in signer_operator_ids],
        )

        self.__submit_aggregated_response(dict(
            task_index=data["task_index"],
            block_number=data["block_number"],
            number_squared=data["number_squared"],
            number_to_be_squared=data["number_to_be_squared"],
            non_signers_pubkeys_g1=non_signers_pubkeys_g1,
            quorum_apks_g1=[quorum_apks_g1],
            signers_apk_g2=signers_apk_g2,
            signers_agg_sig_g1=signers_agg_sig_g1,
            non_signer_quorum_bitmap_indices=indices.non_signer_quorum_bitmap_indices,
            quorum_apk_indices=indices.quorum_apk_indices,
            total_stake_indices=indices.total_stake_indices,
            non_signer_stake_indices=indices.non_signer_stake_indices,
        ))
        return "true", 200

    def __submit_aggregated_response(self, response):
        logger.info(f'Aggregated response {response}')
        task = [
            response['number_to_be_squared'],
            response['block_number'],
            nums_to_bytes([0]),
            100,
        ]
        task_response = [
            response['task_index'],
            response['number_squared']
        ]
        non_signers_stakes_and_signature = [
            response["non_signer_quorum_bitmap_indices"],
            [g1_to_tupple(g1) for g1 in response["non_signers_pubkeys_g1"]],
            [g1_to_tupple(g1) for g1 in response["quorum_apks_g1"]],
            g2_to_tupple(response["signers_apk_g2"]),
            g1_to_tupple(response["signers_agg_sig_g1"]),
            response["quorum_apk_indices"],
            response["total_stake_indices"],
            response["non_signer_stake_indices"],
        ]

        tx = self.task_manager.functions.respondToTask(
            task, task_response, non_signers_stakes_and_signature
        ).build_transaction({
            "from": self.aggregator_address,
            "gas": 2000000,
            "gasPrice": self.web3.to_wei("20", "gwei"),
            "nonce": self.web3.eth.get_transaction_count(
                self.aggregator_address
            ),
            "chainId": self.web3.eth.chain_id,
        })
        signed_tx = self.web3.eth.account.sign_transaction(
            tx, private_key=self.aggregator_ecdsa_private_key
        )
        tx_hash = self.web3.eth.send_raw_transaction(
            signed_tx.raw_transaction
        )
        receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
        logger.info(f"receipt: {receipt}")

    def start_server(self):
        host, port = self.config['aggregator_server_ip_port_address'].split(':')
        self.app.run(host=host, port=port)

    def send_new_task(self, i):
        tx = self.task_manager.functions.createNewTask(
            i, 100, nums_to_bytes([0])
        ).build_transaction({
            "from": self.aggregator_address,
            "gas": 2000000,
            "gasPrice": self.web3.to_wei("20", "gwei"),
            "nonce": self.web3.eth.get_transaction_count(
                self.aggregator_address
            ),
            "chainId": self.web3.eth.chain_id,
        })
        signed_tx = self.web3.eth.account.sign_transaction(
            tx, private_key=self.aggregator_ecdsa_private_key
        )
        tx_hash = self.web3.eth.send_raw_transaction(
            signed_tx.raw_transaction
        )
        receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
        event = self.task_manager.events.NewTaskCreated().process_log(receipt['logs'][0])

        task_index = event['args']['taskIndex']
        logger.info(f"Successfully sent the new task {task_index}")
        return event['args']['taskIndex']

    def start_sending_new_tasks(self):
        i = 0
        while True:
            logger.info('Sending new task')
            task_index = self.send_new_task(i)
            time.sleep(10)
            i += 1

    def __load_ecdsa_key(self):
        ecdsa_key_password = os.environ.get("AGGREGATOR_ECDSA_KEY_PASSWORD", "")
        if not ecdsa_key_password:
            logger.warning("AGGREGATOR_ECDSA_KEY_PASSWORD not set. using empty string.")

        with open(self.config["ecdsa_private_key_store_path"], "r") as f:
            keystore = json.load(f)
        self.aggregator_ecdsa_private_key = Account.decrypt(keystore, ecdsa_key_password).hex()
        self.aggregator_address = Account.from_key(self.aggregator_ecdsa_private_key).address

    def __load_clients(self):
        cfg = BuildAllConfig(
            eth_http_url=self.config["eth_rpc_url"],
            avs_name="incredible-squaring",
            registry_coordinator_addr=self.config["avs_registry_coordinator_address"],
            operator_state_retriever_addr=self.config["operator_state_retriever_address"],
            prom_metrics_ip_port_address="",
        )
        self.clients = build_all(cfg, self.aggregator_ecdsa_private_key, logger)

    def __load_task_manager(self):
        service_manager_address = self.clients.avs_registry_writer.service_manager_addr
        with open("abis/IncredibleSquaringServiceManager.json") as f:
            service_manager_abi = f.read()
        service_manager = self.web3.eth.contract(
            address=service_manager_address, abi=service_manager_abi
        )

        task_manager_address = (
            service_manager.functions.incredibleSquaringTaskManager().call()
        )
        with open("abis/IncredibleSquaringTaskManager.json") as f:
            task_manager_abi = f.read()
        self.task_manager = self.web3.eth.contract(address=task_manager_address, abi=task_manager_abi)

    def __operators_info(self, block):
        query = f"""
        {{
            operators(block: {{ number: {block} }}) {{
                id
                operatorId
                socket
                stake
                pubkeyG1_X
                pubkeyG1_Y
                pubkeyG2_X
                pubkeyG2_Y
            }}
        }}
        """
        response = requests.post(
            self.subgraph_url,
            headers={"content-type": "application/json"},
            json={"query": query},
        )
        response.raise_for_status()

        try:
            operators = response.json()["data"]["operators"]
        except (KeyError, TypeError, ValueError) as e:
            raise RuntimeError(
                f"Unexpected response format while parsing operators: "
                f"{response.text}, error: {e}"
            )

        for op in operators:
            op["public_key_g1"] = G1Point(
                op["pubkeyG1_X"],
                op["pubkeyG1_Y"],
            )
            op["public_key_g2"] = G2Point(
                op["pubkeyG2_X"][0],
                op["pubkeyG2_X"][1],
                op["pubkeyG2_Y"][0],
                op["pubkeyG2_Y"][1],
            )
            op["stake"] = float(op["stake"])

        return {op["operatorId"]: op for op in operators}

if __name__ == '__main__':
    with open("config-files/aggregator.yaml", "r") as f:
        config = yaml.load(f, Loader=yaml.BaseLoader)
    aggregator = Aggregator(config)
    threading.Thread(target=aggregator.start_sending_new_tasks, args=[]).start()
    aggregator.start_server()