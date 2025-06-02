import json
import logging
import os
import threading
import time

import eth_abi
import requests
import yaml
from eigensdk.chainio.clients.builder import BuildAllConfig, build_all
from eigensdk.chainio.utils import nums_to_bytes
from eigensdk.crypto.bls.attestation import (
    Signature,
    G1Point,
    G2Point,
    g1_to_tupple,
    g2_to_tupple,
    new_zero_g1_point,
    new_zero_g2_point,
)
from eth_account import Account
from flask import Flask, request, jsonify
from web3 import Web3

TASK_CHALLENGE_WINDOW_BLOCK = 100
BLOCK_TIME_SECONDS = 12
AVS_NAME = "incredible-squaring"
THRESHOLD_PERCENT = 70

# change logging level to DEBUG for testing
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Define specific error types
class AggregatorError(Exception):
    """Base class for all aggregator errors."""

    pass


class TaskNotFoundError(AggregatorError):
    """Task not found error."""

    def __str__(self):
        return "400. Task not found"


class OperatorNotRegisteredError(AggregatorError):
    """Operator is not registered error."""

    def __str__(self):
        return "400. Operator is not registered"


class OperatorAlreadyProcessedError(AggregatorError):
    """Operator signature has already been processed error."""

    def __str__(self):
        return "400. Operator signature has already been processed"


class SignatureVerificationError(AggregatorError):
    """Signature verification failed error."""

    def __str__(self):
        return "400. Signature verification failed"


class InternalServerError(AggregatorError):
    """Internal server error."""

    def __str__(self):
        return "500. Internal server error"


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
        self.app.add_url_rule(
            "/signature", "signature", self.submit_signature, methods=["POST"]
        )
        self.subgraph_url = "http://localhost:8000/subgraphs/name/avs-subgraph"
        self._stop_flag = False

    def start(self):
        """Start the aggregator service."""
        logger.debug("Starting aggregator.")
        logger.debug("Starting aggregator rpc server.")

        # Start the server in a separate thread
        server_thread = threading.Thread(target=self.start_server)
        server_thread.daemon = True
        server_thread.start()

        # Start sending new tasks
        task_thread = threading.Thread(target=self.start_sending_new_tasks)
        task_thread.daemon = True
        task_thread.start()

        server_thread.join()
        task_thread.join()

    def stop(self):
        """Stop the aggregator service."""
        logger.debug("Stopping aggregator.")
        self._stop_flag = True

    def send_new_task(self, num_to_square):
        """Send a new task to the task manager contract."""
        logger.debug(
            "Aggregator sending new task", extra={"numberToSquare": num_to_square}
        )

        try:
            # Send number to square to the task manager contract
            tx = self.task_manager.functions.createNewTask(
                num_to_square, THRESHOLD_PERCENT, nums_to_bytes([0])
            ).build_transaction(
                {
                    "from": self.aggregator_address,
                    "gas": 2000000,
                    "gasPrice": self.web3.to_wei("20", "gwei"),
                    "nonce": self.web3.eth.get_transaction_count(
                        self.aggregator_address
                    ),
                    "chainId": self.web3.eth.chain_id,
                }
            )

            signed_tx = self.web3.eth.account.sign_transaction(
                tx, private_key=self.aggregator_ecdsa_private_key
            )
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.raw_transaction)
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            event = self.task_manager.events.NewTaskCreated().process_log(
                receipt["logs"][0]
            )

            task_index = event["args"]["taskIndex"]
            self.tasks[task_index] = event["args"]["task"]

            logger.debug(f"Successfully sent the new task {task_index}")
            return task_index

        except Exception as e:
            logger.error(f"Aggregator failed to send number to square: {str(e)}")
            return None

    def start_sending_new_tasks(self):
        """Start sending new tasks periodically."""
        task_num = 0
        while not self._stop_flag:
            logger.debug("Sending new task")
            self.send_new_task(task_num)
            task_num += 1
            time.sleep(10)

    def __verify_signature(self, data, operators):
        """Verify the operator's signature."""
        if data["operator_id"] not in operators:
            raise OperatorNotRegisteredError()

        encoded = eth_abi.encode(
            ["uint32", "uint256"], [data["task_index"], data["number_squared"]]
        )
        task_response_digest = Web3.keccak(encoded)

        pub_key_g2 = operators[data["operator_id"]]["public_key_g2"]
        signature = Signature(data["signature"]["X"], data["signature"]["Y"])
        verified = signature.verify(pub_key_g2, task_response_digest)
        if not verified:
            raise SignatureVerificationError()

    def submit_signature(self):
        """Handle operator signature submission."""
        try:
            data = request.get_json()
            logger.debug(f"Received signed task response: {data}")

            task_index = data["task_index"]
            if task_index not in self.tasks:
                raise TaskNotFoundError()

            operators = self.operators_info(data["block_number"])
            self.__verify_signature(data, operators)

            operator_id = data["operator_id"]

            if task_index not in self.responses:
                self.responses[task_index] = {}

            if operator_id in self.responses[task_index]:
                raise OperatorAlreadyProcessedError()

            self.responses[task_index][operator_id] = data
            signer_operator_ids = [
                operator_id
                for operator_id in self.responses[task_index]
                if self.responses[task_index][operator_id]["number_squared"]
                == data["number_squared"]
            ]

            signed_stake = sum(
                operators[operator_id]["stake"] for operator_id in signer_operator_ids
            )
            total_stake = sum(
                operators[operator_id]["stake"] for operator_id in operators
            )

            logger.debug(
                f"Signature processed successfully",
                extra={
                    "taskIndex": task_index,
                    "operatorId": operator_id,
                    "signedStake": signed_stake,
                    "totalStake": total_stake,
                    "threshold": THRESHOLD_PERCENT,
                },
            )

            if total_stake > 0 and signed_stake / total_stake < THRESHOLD_PERCENT / 100:
                return (
                    jsonify(
                        {
                            "success": True,
                            "message": "Signature accepted, threshold not yet reached",
                        }
                    ),
                    200,
                )

            # Process the aggregated response
            signatures = [
                self.responses[task_index][operator_id]["signature"]
                for operator_id in signer_operator_ids
            ]
            non_signers_pubkeys_g1 = [
                operators[operator_id]["public_key_g1"]
                for operator_id in operators
                if operator_id not in signer_operator_ids
            ]
            quorum_apks_g1 = sum(
                [operators[operator_id]["public_key_g1"] for operator_id in operators],
                new_zero_g1_point(),
            )
            signers_apk_g2 = sum(
                [
                    operators[operator_id]["public_key_g2"]
                    for operator_id in operators
                    if operator_id in signer_operator_ids
                ],
                new_zero_g2_point(),
            )
            signers_agg_sig_g1 = sum(
                [Signature(signature["X"], signature["Y"]) for signature in signatures],
                new_zero_g1_point(),
            )

            indices = self.clients.avs_registry_reader.get_check_signatures_indices(
                data["block_number"],
                [0],
                [
                    int(operator_id, 16)
                    for operator_id in operators
                    if operator_id not in signer_operator_ids
                ],
            )

            self.__submit_aggregated_response(
                {
                    "task_index": data["task_index"],
                    "block_number": data["block_number"],
                    "number_squared": data["number_squared"],
                    "number_to_be_squared": self.tasks[task_index]["numberToBeSquared"],
                    "non_signers_pubkeys_g1": non_signers_pubkeys_g1,
                    "quorum_apks_g1": [quorum_apks_g1],
                    "signers_apk_g2": signers_apk_g2,
                    "signers_agg_sig_g1": signers_agg_sig_g1,
                    "non_signer_quorum_bitmap_indices": indices[0],
                    "quorum_apk_indices": indices[1],
                    "total_stake_indices": indices[2],
                    "non_signer_stake_indices": indices[3],
                }
            )
            return (
                jsonify(
                    {
                        "success": True,
                        "message": "Threshold reached, aggregated response submitted",
                    }
                ),
                200,
            )

        except TaskNotFoundError as e:
            logger.error(f"Task not found: {str(e)}")
            return jsonify({"success": False, "error": str(e)}), 400
        except OperatorNotRegisteredError as e:
            logger.error(f"Operator not registered: {str(e)}")
            return jsonify({"success": False, "error": str(e)}), 400
        except OperatorAlreadyProcessedError as e:
            logger.error(f"Operator already processed: {str(e)}")
            return jsonify({"success": False, "error": str(e)}), 400
        except SignatureVerificationError as e:
            logger.error(f"Signature verification failed: {str(e)}")
            return jsonify({"success": False, "error": str(e)}), 400
        except Exception as e:
            logger.error(f"Internal server error: {str(e)}")
            return (
                jsonify({"success": False, "error": "500. Internal server error"}),
                500,
            )

    def __submit_aggregated_response(self, response):
        """Submit aggregated response to the contract."""
        logger.debug(
            f"Submitting aggregated response to contract",
            extra={"taskIndex": response["task_index"]},
        )

        task = [
            response["number_to_be_squared"],
            response["block_number"],
            nums_to_bytes([0]),
            THRESHOLD_PERCENT,
        ]
        task_response = [response["task_index"], response["number_squared"]]
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

        try:
            tx = self.task_manager.functions.respondToTask(
                task, task_response, non_signers_stakes_and_signature
            ).build_transaction(
                {
                    "from": self.aggregator_address,
                    "gas": 2000000,
                    "gasPrice": self.web3.to_wei("20", "gwei"),
                    "nonce": self.web3.eth.get_transaction_count(
                        self.aggregator_address
                    ),
                    "chainId": self.web3.eth.chain_id,
                }
            )
            signed_tx = self.web3.eth.account.sign_transaction(
                tx, private_key=self.aggregator_ecdsa_private_key
            )
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.raw_transaction)
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            logger.debug(
                "Aggregated response sent successfully",
                extra={"txHash": receipt["transactionHash"].hex()},
            )
        except Exception as e:
            logger.error(f"Failed to submit aggregated response: {str(e)}")
            raise

    def start_server(self):
        """Start the Flask server."""
        host, port = self.config["aggregator_server_ip_port_address"].split(":")
        self.app.run(host=host, port=int(port), use_reloader=False)

    def __load_ecdsa_key(self):
        """Load the ECDSA private key."""
        ecdsa_key_password = os.environ.get("AGGREGATOR_ECDSA_KEY_PASSWORD", "")
        if not ecdsa_key_password:
            logger.warning("AGGREGATOR_ECDSA_KEY_PASSWORD not set. using empty string.")

        with open(self.config["ecdsa_private_key_store_path"], "r") as f:
            keystore = json.load(f)
        self.aggregator_ecdsa_private_key = Account.decrypt(
            keystore, ecdsa_key_password
        ).hex()
        self.aggregator_address = Account.from_key(
            self.aggregator_ecdsa_private_key
        ).address

    def __load_clients(self):
        """Load the AVS clients."""
        cfg = BuildAllConfig(
            eth_http_url=self.config["eth_rpc_url"],
            avs_name=AVS_NAME,
            registry_coordinator_addr=self.config["avs_registry_coordinator_address"],
            operator_state_retriever_addr=self.config[
                "operator_state_retriever_address"
            ],
            rewards_coordinator_addr=self.config["rewards_coordinator_address"],
            permission_controller_addr=self.config["permission_controller_address"],
            service_manager_addr=self.config["service_manager_address"],
            allocation_manager_addr=self.config["allocation_manager_address"],
            instant_slasher_addr=self.config["instant_slasher_address"],
            delegation_manager_addr=self.config["delegation_manager_address"],
            prom_metrics_ip_port_address=self.config["prom_metrics_ip_port_address"],
        )
        self.clients = build_all(cfg, self.aggregator_ecdsa_private_key)

    def __load_task_manager(self):
        """Load the task manager contract."""
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
        self.task_manager = self.web3.eth.contract(
            address=task_manager_address, abi=task_manager_abi
        )

    def operators_info(self, block):
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


if __name__ == "__main__":
    with open("config-files/aggregator.yaml", "r") as f:
        config = yaml.load(f, Loader=yaml.BaseLoader)
    aggregator = Aggregator(config)
    aggregator.start()
