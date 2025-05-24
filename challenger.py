from typing import Dict, List, Optional
from dataclasses import dataclass
import logging
import json
import os
from web3 import Web3
import eth_abi
from eth_account import Account
from eigensdk.chainio.clients.builder import BuildAllConfig, build_all
import yaml

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class Task:
    number_to_be_squared: int

@dataclass
class TaskResponse:
    number_squared: int
    reference_task_index: int

@dataclass
class TaskResponseData:
    task_response: TaskResponse
    task_response_metadata: dict
    non_signing_operator_pub_keys: List[dict]

# Define specific error types
class ChallengerError(Exception):
    """Base class for all challenger errors."""
    pass

class KeyLoadError(ChallengerError):
    """Key load error."""
    pass

class TaskNotFoundError(ChallengerError):
    """Task not found error."""
    def __str__(self):
        return "400. Task not found"

class TransactionError(ChallengerError):
    """Transaction related error."""
    def __str__(self):
        return "500. Failed to execute transaction"

class TaskResponseParsingError(ChallengerError):
    """Failed to parse task response error."""
    def __str__(self):
        return "500. Failed to parse task response"

class NoErrorInTaskResponse(ChallengerError):
    """Task response is valid, no error found."""
    def __str__(self):
        return "100. Task response is valid"

class Challenger:
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.__load_ecdsa_key()
        self.__load_clients()
        self.__load_task_manager()
        self.tasks: Dict[int, Task] = {}
        self.task_responses: Dict[int, TaskResponseData] = {}
        self.task_response_channel = None
        self.new_task_created_channel = None

    def start(self, context) -> None:
        """Start the challenger service."""
        self.logger.info("Starting Challenger.")

        # Subscribe to new tasks
        new_task_sub = self.avs_subscriber.subscribe_to_new_tasks(self.new_task_created_channel)
        self.logger.info("Subscribed to new tasks")

        # Subscribe to task responses
        task_response_sub = self.avs_subscriber.subscribe_to_task_responses(self.task_response_channel)
        self.logger.info("Subscribed to task responses")

        while True:
            try:
                # Handle new task created events
                for event in new_task_sub.get_new_entries():
                    self.logger.info(
                        "New task created log received",
                        extra={
                            "taskIndex": event["args"]["taskIndex"],
                            "task": event["args"]["task"]
                        }
                    )
                    task_index = self.process_new_task_created_log(event)

                    if task_index in self.task_responses:
                        try:
                            self.call_challenge_module(task_index)
                        except NoErrorInTaskResponse:
                            self.logger.info("No error found in task response")
                        except ChallengerError as e:
                            self.logger.error(f"Error in challenge module: {str(e)}")
                        except Exception as e:
                            self.logger.error(f"Unexpected error in challenge module: {str(e)}")

                # Handle task response events
                for event in task_response_sub.get_new_entries():
                    self.logger.info("Task response log received", extra={"taskResponse": event["args"]["taskResponse"]})
                    try:
                        task_index = self.process_task_response_log(event)

                        if task_index in self.tasks:
                            try:
                                self.call_challenge_module(task_index)
                            except NoErrorInTaskResponse:
                                self.logger.info("No error found in task response")
                            except ChallengerError as e:
                                self.logger.error(f"Error in challenge module: {str(e)}")
                            except Exception as e:
                                self.logger.error(f"Unexpected error in challenge module: {str(e)}")
                    except TaskResponseParsingError as e:
                        self.logger.error(f"Failed to process task response: {str(e)}")
                    except Exception as e:
                        self.logger.error(f"Unexpected error processing task response: {str(e)}")

            except Exception as e:
                self.logger.error(f"Error in event processing: {str(e)}")
                # Resubscribe on error
                new_task_sub = self.avs_subscriber.subscribe_to_new_tasks(self.new_task_created_channel)
                task_response_sub = self.avs_subscriber.subscribe_to_task_responses(self.task_response_channel)

    def process_new_task_created_log(self, new_task_created_log) -> int:
        """Process new task creation log."""
        task_index = new_task_created_log["args"]["taskIndex"]
        task = Task(number_to_be_squared=new_task_created_log["args"]["task"]["numberToBeSquared"])
        self.tasks[task_index] = task
        self.logger.debug(f"Processed new task {task_index} with number to be squared: {task.number_to_be_squared}")
        return task_index

    def process_task_response_log(self, task_response_log) -> int:
        """Process task response log."""
        task_response_raw_log = self.avs_subscriber.parse_task_responded(task_response_log["raw"])
        if not task_response_raw_log:
            self.logger.error(
                "Error parsing task response. skipping task (this is probably bad and should be investigated)"
            )
            raise TaskResponseParsingError()

        # Get the inputs necessary for raising a challenge
        non_signing_operator_pub_keys = self.get_non_signing_operator_pub_keys(task_response_log)
        task_response = TaskResponse(
            number_squared=task_response_log["args"]["taskResponse"]["numberSquared"],
            reference_task_index=task_response_log["args"]["taskResponse"]["referenceTaskIndex"]
        )
        task_response_data = TaskResponseData(
            task_response=task_response,
            task_response_metadata=task_response_log["args"]["taskResponseMetadata"],
            non_signing_operator_pub_keys=non_signing_operator_pub_keys
        )

        task_index = task_response_raw_log["args"]["taskResponse"]["referenceTaskIndex"]
        self.task_responses[task_index] = task_response_data
        self.logger.debug(f"Processed task response for task {task_index} with number squared: {task_response.number_squared}")
        return task_index

    def call_challenge_module(self, task_index: int) -> Optional[Exception]:
        """Call the challenge module for a given task."""
        if task_index not in self.tasks:
            raise TaskNotFoundError()

        number_to_be_squared = self.tasks[task_index].number_to_be_squared
        answer_in_response = self.task_responses[task_index].task_response.number_squared
        true_answer = number_to_be_squared ** 2

        # Check if the answer in the response submitted by aggregator is correct
        if true_answer != answer_in_response:
            self.logger.info(
                "The number squared is not correct",
                extra={
                    "expectedAnswer": true_answer,
                    "gotAnswer": answer_in_response
                }
            )

            # Raise challenge
            self.raise_challenge(task_index)
            return None
        else:
            self.logger.info("The number squared is correct")
            raise NoErrorInTaskResponse()

    def get_non_signing_operator_pub_keys(self, v_log) -> List[dict]:
        """Get public keys of non-signing operators."""
        # Get the nonSignerStakesAndSignature
        tx_hash = v_log["transactionHash"]
        try:
            tx = self.eth_http_client.eth.get_transaction(tx_hash)
            if not tx:
                self.logger.error(
                    "Error getting transaction by hash",
                    extra={
                        "txHash": tx_hash
                    }
                )
                return []

            calldata = tx["input"]
            with open("abis/IncredibleSquaringTaskManager.json") as f:
                task_manager_abi = json.load(f)
            
            method_sig = calldata[:10]  # First 4 bytes (8 hex chars) + 0x
            method = None
            for abi_item in task_manager_abi:
                if abi_item["type"] == "function":
                    # Get the function signature
                    inputs = ",".join([input["type"] for input in abi_item["inputs"]])
                    sig = f"{abi_item['name']}({inputs})"
                    if Web3.keccak(text=sig)[:4].hex() == method_sig[2:]:
                        method = abi_item
                        break

            if not method:
                self.logger.error("Error getting method")
                return []

            inputs = eth_abi.decode(method["inputs"], bytes.fromhex(calldata[10:]))
            non_signer_stakes_and_signature_input = inputs[2]  # Assuming this is the third parameter

            # Get pubkeys of non-signing operators
            non_signing_operator_pub_keys = []
            for pubkey in non_signer_stakes_and_signature_input["nonSignerPubkeys"]:
                non_signing_operator_pub_keys.append({
                    "X": pubkey["X"],
                    "Y": pubkey["Y"]
                })

            return non_signing_operator_pub_keys

        except Exception as e:
            self.logger.error(f"Error getting non-signing operator pubkeys: {str(e)}")
            return []

    def raise_challenge(self, task_index: int) -> None:
        """Raise a challenge for a given task."""
        self.logger.info("Challenger raising challenge.", extra={"taskIndex": task_index})
        self.logger.debug("Task", extra={"Task": self.tasks[task_index]})
        self.logger.debug("TaskResponse", extra={"TaskResponse": self.task_responses[task_index].task_response})
        self.logger.debug("TaskResponseMetadata", extra={"TaskResponseMetadata": self.task_responses[task_index].task_response_metadata})
        self.logger.debug(
            "NonSigningOperatorPubKeys",
            extra={"NonSigningOperatorPubKeys": self.task_responses[task_index].non_signing_operator_pub_keys}
        )

        try:
            receipt = self.avs_writer.raise_challenge(
                self.tasks[task_index],
                self.task_responses[task_index].task_response,
                self.task_responses[task_index].task_response_metadata,
                self.task_responses[task_index].non_signing_operator_pub_keys
            )
            self.logger.info("Challenge raised", extra={"challengeTxHash": receipt["transactionHash"].hex()})
        except Exception as e:
            self.logger.error(f"Challenger failed to raise challenge: {str(e)}")
            raise TransactionError()

    def __load_ecdsa_key(self):
        """Load the ECDSA private key"""
        try:
            ecdsa_key_password = os.environ.get("CHALLENGER_ECDSA_KEY_PASSWORD", "")
            if not ecdsa_key_password:
                logger.warning("CHALLENGER_ECDSA_KEY_PASSWORD not set. using empty string.")

            if not os.path.exists(self.config["ecdsa_private_key_store_path"]):
                logger.error(f"ECDSA key file not found at: {self.config['ecdsa_private_key_store_path']}")
                raise KeyLoadError(f"ECDSA key file not found")

            with open(self.config["ecdsa_private_key_store_path"], "r") as f:
                keystore = json.load(f)
            self.challenger_ecdsa_private_key = Account.decrypt(keystore, ecdsa_key_password).hex()
            self.challenger_address = Account.from_key(self.challenger_ecdsa_private_key).address
            logger.info(f"Loaded ECDSA key for address: {self.challenger_address}")
        except Exception as e:
            logger.error(f"Failed to load ECDSA key: {str(e)}")
            raise KeyLoadError(f"Failed to load ECDSA key: {str(e)}")

    def __load_clients(self):
        """Load the AVS clients."""
        try:
            cfg = BuildAllConfig(
                eth_http_url=self.config["eth_rpc_url"],
                avs_name="incredible-squaring",
                registry_coordinator_addr=self.config["avs_registry_coordinator_address"],
                operator_state_retriever_addr=self.config["operator_state_retriever_address"],
                rewards_coordinator_addr=self.config["rewards_coordinator_address"],
                permission_controller_addr=self.config["permission_controller_address"],
                service_manager_addr=self.config["service_manager_address"],
                allocation_manager_addr=self.config["allocation_manager_address"],
                instant_slasher_addr=self.config["instant_slasher_address"],
                delegation_manager_addr=self.config["delegation_manager_address"],
                prom_metrics_ip_port_address=self.config["prom_metrics_ip_port_address"],
            )
            self.clients = build_all(cfg, self.challenger_ecdsa_private_key)
            self.avs_registry_reader = self.clients.avs_registry_reader
            self.avs_registry_writer = self.clients.avs_registry_writer
            self.el_reader = self.clients.el_reader
            self.el_writer = self.clients.el_writer
            self.eth_http_client = self.clients.eth_http_client
            self.logger.info("Successfully loaded AVS clients")
        except Exception as e:
            self.logger.error(f"Failed to load AVS clients: {str(e)}")
            raise

    def __load_task_manager(self):
        """Load the task manager contract."""
        try:
            service_manager_address = self.clients.avs_registry_writer.service_manager_addr
            with open("abis/IncredibleSquaringServiceManager.json") as f:
                service_manager_abi = f.read()
            service_manager = self.eth_http_client.eth.contract(
                address=service_manager_address, abi=service_manager_abi
            )

            task_manager_address = (
                service_manager.functions.incredibleSquaringTaskManager().call()
            )
            with open("abis/IncredibleSquaringTaskManager.json") as f:
                task_manager_abi = f.read()
            self.task_manager = self.eth_http_client.eth.contract(address=task_manager_address, abi=task_manager_abi)
            self.logger.info(f"Task manager loaded at address: {task_manager_address}")
        except Exception as e:
            self.logger.error(f"Failed to load task manager: {str(e)}")
            raise


if __name__ == '__main__':
    try:
        config_path = "config-files/challenger.yaml"
        if not os.path.exists(config_path):
            logger.error(f"Config file not found at: {config_path}")
            raise FileNotFoundError(f"Config file not found at: {config_path}")
            
        with open(config_path, "r") as f:
            config = yaml.load(f, Loader=yaml.BaseLoader)
            
        challenger = Challenger(config)
        challenger.start(None)
    except Exception as e:
        logger.error(f"Error in challenger: {str(e)}")
