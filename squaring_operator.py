import json
import logging
import os
import time

import eth_abi
import requests
import yaml
from eigensdk.chainio.clients.builder import BuildAllConfig, build_all
from eigensdk.crypto.bls.attestation import KeyPair
from eigensdk.types_ import Operator
from eth_account import Account
from eth_typing import Address
from web3 import Web3

# change logging level to DEBUG for testing
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SquaringOperator:
    def __init__(self, config):
        self.config = config
        self.times_failing = int(config.get("times_failing", 0))
        self.bls_key_pair = None
        self.operator_ecdsa_private_key = None
        self.operator_address = None
        self.clients = None
        self.task_manager = None
        self.web3 = None
        self.operator_id = None
        self._stop_flag = False

        self.__load_bls_key()
        self.__load_ecdsa_key()
        self.__load_clients()
        self.__load_task_manager()

        if config.get("register_operator_on_startup") == "true":
            self.register_operator_on_startup()

        # operator id can only be loaded after registration
        self.__load_operator_id()
        logger.debug("Operator initialized successfully")

    def register_operator_on_startup(self):
        """Register operator with EigenLayer and AVS on startup"""
        logger.debug("Registering operator on startup")
        self.register_operator_with_eigenlayer()
        logger.debug("Registered operator with eigenlayer")
        amount = int(1e21)  # 1000 tokens with 18 decimals
        strategy_addr = self.config.get("token_strategy_addr")
        self.deposit_into_strategy(strategy_addr, amount)
        logger.debug(f"Deposited {amount} into strategy {strategy_addr}")
        self.register_for_operator_sets([0])  # Default to quorum 0
        logger.debug("Registered operator with AVS")
        self.set_allocation_delay(0)
        logger.debug("Set allocation delay to 0")
        strategies = [self.config.get("token_strategy_addr")]
        new_magnitudes = [100000000]
        self.modify_allocations(strategies, new_magnitudes, 0)
        logger.debug("Modified allocations successfully")

    def stop(self):
        """Stop the operator service"""
        logger.debug("Stopping Operator...")
        self._stop_flag = True

    def start(self):
        """Start the operator service"""
        logger.debug("Starting Operator...")

        if self.task_manager is None:
            raise RuntimeError("Task manager not loaded")

        event_filter = self.task_manager.events.NewTaskCreated.create_filter(
            from_block="latest"
        )

        logger.debug("Listening for new tasks...")
        while not self._stop_flag:
            try:
                for event in event_filter.get_new_entries():
                    logger.debug(f"New task created: {event}")
                    try:
                        task_response = self.process_task_event(event)
                        signed_response = self.sign_task_response(task_response)
                        self.send_signed_task_response(signed_response)
                    except Exception as e:
                        logger.error(f"Unexpected error handling task: {str(e)}")

                time.sleep(3)
            except Exception as e:
                logger.error(f"Error in event processing loop: {str(e)}")
                time.sleep(5)

    def process_task_event(self, event):
        """Process a new task event and generate a task response"""
        logger.debug(
            "Processing new task",
            extra={
                "numberToBeSquared": event["args"]["task"]["numberToBeSquared"],
                "taskIndex": event["args"]["taskIndex"],
                "taskCreatedBlock": event["args"]["task"]["taskCreatedBlock"],
                "quorumNumbers": event["args"]["task"]["quorumNumbers"],
                "QuorumThresholdPercentage": event["args"]["task"][
                    "quorumThresholdPercentage"
                ],
            },
        )

        task_index = event["args"]["taskIndex"]
        number_to_be_squared = event["args"]["task"]["numberToBeSquared"]
        number_squared = number_to_be_squared**2

        # Optional: Simulate failures if configured
        if self.times_failing > 0:
            import random

            if random.randint(0, 99) < self.times_failing:
                number_squared = 908243203843
                logger.debug("Operator computed wrong task result")

        task_response = {
            "referenceTaskIndex": task_index,
            "numberSquared": number_squared,
        }

        return task_response

    def sign_task_response(self, task_response):
        """Sign a task response with the operator's BLS key"""
        if self.bls_key_pair is None:
            raise RuntimeError("BLS key pair not loaded")

        encoded = eth_abi.encode(
            ["uint32", "uint256"],
            [task_response["referenceTaskIndex"], task_response["numberSquared"]],
        )
        hash_bytes = Web3.keccak(encoded)
        signature = self.bls_key_pair.sign_message(msg_bytes=hash_bytes).to_json()

        logger.debug(
            f"Signature generated, task id: {task_response['referenceTaskIndex']}, "
            f"number squared: {task_response['numberSquared']}"
        )

        signed_response = {
            "taskResponse": task_response,
            "blsSignature": signature,
            "operatorId": self.operator_id.hex() if self.operator_id else None,
        }

        return signed_response

    def send_signed_task_response(self, signed_response):
        """Send a signed task response to the aggregator"""
        logger.debug("Submitting task response to aggregator")

        if self.web3 is None:
            raise RuntimeError("Web3 instance not loaded")

        data = {
            "task_index": signed_response["taskResponse"]["referenceTaskIndex"],
            "number_squared": signed_response["taskResponse"]["numberSquared"],
            "signature": signed_response["blsSignature"],
            "block_number": self.web3.eth.block_number,
            "operator_id": "0x" + (signed_response["operatorId"] or ""),
        }

        # Wait briefly to ensure the aggregator has processed the task
        time.sleep(3)

        try:
            url = f'http://{self.config["aggregator_server_ip_port_address"]}/signature'
            response = requests.post(url, json=data)
            response.raise_for_status()
            logger.debug(
                f"Successfully sent task response to aggregator, response: {response.text}"
            )
        except Exception as e:
            logger.error(f"Unknown error sending task response: {str(e)}")

    def register_operator_with_eigenlayer(self):
        if self.clients is None:
            raise RuntimeError("Clients not loaded")

        operator = Operator(
            address=self.config["operator_address"],
            earnings_receiver_address=self.config["operator_address"],
            delegation_approver_address=self.config["operator_address"],
            allocation_delay=0,
            staker_opt_out_window_blocks=0,
            metadata_url="",
        )
        return self.clients.el_writer.register_as_operator(operator)

    def deposit_into_strategy(self, strategy_addr, amount):
        if self.clients is None:
            raise RuntimeError("Clients not loaded")
        return self.clients.el_writer.deposit_erc20_into_strategy(strategy_addr, amount)

    def register_for_operator_sets(self, operator_set_ids):
        """Register the operator for operator sets"""
        if self.clients is None:
            raise RuntimeError("Clients not loaded")

        request = {
            "operator_address": self.config["operator_address"],
            "avs_address": self.config["service_manager_address"],
            "operator_set_ids": operator_set_ids,
            "socket": "operator-socket",
            "bls_key_pair": self.bls_key_pair,
        }
        self.clients.el_writer.register_for_operator_sets(
            self.config["avs_registry_coordinator_address"], request
        )

    def deregister_from_operator_sets(self, operator_set_ids):
        if self.clients is None:
            raise RuntimeError("Clients not loaded")

        request = {
            "avs_address": self.config["service_manager_address"],
            "operator_set_ids": operator_set_ids,
        }
        receipt = self.clients.el_writer.deregister_from_operator_sets(
            self.operator_address, request
        )
        return receipt

    def modify_allocations(self, strategies, new_magnitudes, operator_set_id):
        """Modify allocations for the operator"""
        if self.clients is None:
            raise RuntimeError("Clients not loaded")

        avs_service_manager = self.config.get("service_manager_address")
        if not avs_service_manager:
            logger.error("Service manager address not configured")
            return

        self.clients.el_writer.modify_allocations(
            Web3.to_checksum_address(self.config["operator_address"]),
            avs_service_manager,
            operator_set_id,
            strategies,
            new_magnitudes,
        )

    def set_allocation_delay(self, delay):
        """Set allocation delay for the operator"""
        if self.clients is None:
            raise RuntimeError("Clients not loaded")
        self.clients.el_writer.set_allocation_delay(
            Web3.to_checksum_address(self.config["operator_address"]), delay
        )

    def set_appointee(
        self,
        account_address: Address,
        appointee_address: Address,
        target: Address,
        selector: str,
    ):
        """Set the appointee for the operator"""
        if self.clients is None:
            raise RuntimeError("Clients not loaded")

        self.clients.el_writer.set_permission(
            {
                "account_address": account_address,
                "appointee_address": appointee_address,
                "target": target,
                "selector": selector,
            }
        )

    def create_total_delegated_stake_quorum(
        self, operator_set_params, minimum_stake_required, strategy_params
    ):
        """Create a total delegated stake quorum for the operator

        Args:
            operator_set_params: Tuple of (MaxOperatorCount, KickBIPsOfOperatorStake, KickBIPsOfTotalStake)
            minimum_stake_required: Minimum stake required for the quorum
            strategy_params: List of tuples (strategy_address, weight)
        """
        if self.clients is None:
            raise RuntimeError("Clients not loaded")

        receipt = self.clients.avs_registry_writer.create_total_delegated_stake_quorum(
            operator_set_params, minimum_stake_required, strategy_params
        )
        return receipt

    def __load_bls_key(self):
        """Load the BLS key pair"""
        bls_key_password = os.environ.get("OPERATOR_BLS_KEY_PASSWORD", "")

        self.bls_key_pair = KeyPair.read_from_file(
            self.config["bls_private_key_store_path"], bls_key_password
        )
        logger.debug(
            f"BLS PubG1: {self.bls_key_pair.pub_g1.getStr()} PubG2: {self.bls_key_pair.pub_g2.getStr()}"
        )

    def __load_ecdsa_key(self):
        """Load the ECDSA private key"""
        ecdsa_key_password = os.environ.get("OPERATOR_ECDSA_KEY_PASSWORD", "")

        with open(self.config["ecdsa_private_key_store_path"], "r") as f:
            keystore = json.load(f)
        self.operator_ecdsa_private_key = Account.decrypt(
            keystore, ecdsa_key_password
        ).hex()
        self.operator_address = Account.from_key(
            self.operator_ecdsa_private_key
        ).address
        logger.debug(f"Loaded ECDSA key for address: {self.operator_address}")

    def __load_clients(self):
        """Load the AVS clients"""
        if self.operator_ecdsa_private_key is None:
            raise RuntimeError("ECDSA private key not loaded")

        cfg = BuildAllConfig(
            eth_http_url=self.config["eth_rpc_url"],
            avs_name="incredible-squaring",
            registry_coordinator_addr=self.config["avs_registry_coordinator_address"],
            operator_state_retriever_addr=self.config[
                "operator_state_retriever_address"
            ],
            rewards_coordinator_addr=self.config["rewards_coordinator_address"],
            permission_controller_addr=self.config["permission_controller_address"],
            service_manager_addr=self.config["service_manager_address"],
            allocation_manager_addr=self.config["allocation_manager_address"],
            delegation_manager_addr=self.config["delegation_manager_address"],
        )
        self.clients = build_all(cfg, self.operator_ecdsa_private_key)
        self.web3 = Web3(Web3.HTTPProvider(self.config["eth_rpc_url"]))
        logger.debug("Successfully loaded AVS clients")

    def __load_task_manager(self):
        """Load the task manager contract"""
        if self.clients is None:
            raise RuntimeError("Clients not loaded")
        if self.web3 is None:
            raise RuntimeError("Web3 instance not loaded")

        service_manager_address = self.clients.avs_registry_writer.service_manager_addr

        service_manager_abi_path = "abis/IncredibleSquaringServiceManager.json"
        if not os.path.exists(service_manager_abi_path):
            logger.error(
                f"Service manager ABI file not found at: {service_manager_abi_path}"
            )

        with open(service_manager_abi_path) as f:
            service_manager_abi = f.read()

        service_manager = self.web3.eth.contract(
            address=service_manager_address, abi=service_manager_abi
        )

        task_manager_address = (
            service_manager.functions.incredibleSquaringTaskManager().call()
        )

        task_manager_abi_path = "abis/IncredibleSquaringTaskManager.json"
        if not os.path.exists(task_manager_abi_path):
            logger.error(f"Task manager ABI file not found at: {task_manager_abi_path}")

        with open(task_manager_abi_path) as f:
            task_manager_abi = f.read()

        self.task_manager = self.web3.eth.contract(
            address=task_manager_address, abi=task_manager_abi
        )
        logger.debug(f"Task manager loaded at address: {task_manager_address}")

    def __load_operator_id(self):
        """Load the operator ID"""
        if self.clients is None:
            raise RuntimeError("Clients not loaded")

        self.operator_id = self.clients.avs_registry_reader.get_operator_id(
            self.config["operator_address"]
        )
        logger.debug(
            f"Loaded operator ID: {self.operator_id.hex() if self.operator_id else None}"
        )


if __name__ == "__main__":
    dir_path = os.path.dirname(os.path.abspath(__file__))

    operator_config_path = os.path.join(dir_path, "./config-files/operator1.yaml")
    if not os.path.exists(operator_config_path):
        logger.error(f"Config file not found at: {operator_config_path}")
        raise FileNotFoundError(f"Config file not found at: {operator_config_path}")
    with open(operator_config_path, "r") as f:
        operator_config = yaml.load(f, Loader=yaml.BaseLoader)

    avs_config_path = os.path.join(dir_path, "./config-files/avs.yaml")
    if not os.path.exists(avs_config_path):
        logger.error(f"Config file not found at: {avs_config_path}")
        raise FileNotFoundError(f"Config file not found at: {avs_config_path}")
    with open(avs_config_path, "r") as f:
        avs_config = yaml.load(f, Loader=yaml.BaseLoader)

    operator = SquaringOperator(config={**operator_config, **avs_config})
    operator.start()
