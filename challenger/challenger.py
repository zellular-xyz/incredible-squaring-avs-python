import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

import yaml
from eigensdk.chainio.clients.builder import BuildAllConfig, build_all
from eth_account import Account

# change logging level to DEBUG for testing
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class Task:
    number_to_be_squared: int
    task_created_block: int
    quorum_numbers: bytes
    quorum_threshold_percentage: int

    def to_tuple(self):
        return (
            self.number_to_be_squared,
            self.task_created_block,
            self.quorum_numbers,
            self.quorum_threshold_percentage,
        )


@dataclass
class TaskResponse:
    number_squared: int
    reference_task_index: int

    def to_tuple(self):
        return (self.reference_task_index, self.number_squared)


@dataclass
class TaskResponseMetadata:
    task_responsed_block: int
    hash_of_non_signers: bytes

    def to_tuple(self):
        return (self.task_responsed_block, self.hash_of_non_signers)


@dataclass
class TaskResponseData:
    task_response: TaskResponse
    task_response_metadata: TaskResponseMetadata
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
        self.__load_ecdsa_key()
        self.__load_clients()
        self.__load_task_manager()
        self.tasks: Dict[int, Task] = {}
        self.task_responses: Dict[int, TaskResponseData] = {}
        self.task_response_channel = None
        self.new_task_created_channel = None

    def start(self, context) -> None:
        """Start the challenger service."""
        logger.debug("Starting Challenger.")

        # Subscribe to new tasks
        new_task_sub = self.task_manager.events.NewTaskCreated.create_filter(
            from_block="latest"
        )

        # Subscribe to task responses
        task_response_sub = self.task_manager.events.TaskResponded.create_filter(
            from_block="latest"
        )

        logger.debug("Listening for new events...")
        while True:
            try:
                # Handle new task created events
                for event in new_task_sub.get_new_entries():
                    logger.debug(
                        "New task created log received",
                        extra={
                            "taskIndex": event["args"]["taskIndex"],
                            "task": event["args"]["task"],
                        },
                    )
                    task_index = self.process_new_task_created_log(event)

                    if task_index in self.task_responses:
                        try:
                            self.call_challenge_module(task_index)
                        except NoErrorInTaskResponse:
                            logger.debug("No error found in task response")
                        except ChallengerError as e:
                            logger.error(f"Error in challenge module: {str(e)}")
                        except Exception as e:
                            logger.error(
                                f"Unexpected error in challenge module: {str(e)}"
                            )

                # Handle task response events
                for event in task_response_sub.get_new_entries():
                    logger.debug(
                        "Task response log received",
                        extra={"taskResponse": event["args"]["taskResponse"]},
                    )
                    try:
                        task_index = self.process_task_response_log(event)

                        if task_index in self.tasks:
                            try:
                                self.call_challenge_module(task_index)
                            except NoErrorInTaskResponse:
                                logger.debug("No error found in task response")
                            except ChallengerError as e:
                                logger.error(f"Error in challenge module: {str(e)}")
                            except Exception as e:
                                logger.error(
                                    f"Unexpected error in challenge module: {str(e)}"
                                )
                    except TaskResponseParsingError as e:
                        logger.error(f"Failed to process task response: {str(e)}")
                    except Exception as e:
                        logger.error(
                            f"Unexpected error processing task response: {str(e)}"
                        )
                time.sleep(3)

            except Exception as e:
                logger.error(f"Error in event processing: {str(e)}")
                time.sleep(5)

    def process_new_task_created_log(self, new_task_created_log) -> int:
        """Process new task creation log."""
        task_index = new_task_created_log["args"]["taskIndex"]
        task = Task(
            number_to_be_squared=new_task_created_log["args"]["task"][
                "numberToBeSquared"
            ],
            task_created_block=new_task_created_log["args"]["task"]["taskCreatedBlock"],
            quorum_numbers=new_task_created_log["args"]["task"]["quorumNumbers"],
            quorum_threshold_percentage=new_task_created_log["args"]["task"][
                "quorumThresholdPercentage"
            ],
        )
        self.tasks[task_index] = task
        logger.debug(
            f"Processed new task {task_index} with number to be squared: {task.number_to_be_squared}"
        )
        return task_index

    def process_task_response_log(self, task_response_log) -> int:
        """Process task response log."""
        # Get the inputs necessary for raising a challenge
        non_signing_operator_pub_keys = self.get_non_signing_operator_pub_keys(
            task_response_log
        )
        task_response = TaskResponse(
            number_squared=task_response_log["args"]["taskResponse"]["numberSquared"],
            reference_task_index=task_response_log["args"]["taskResponse"][
                "referenceTaskIndex"
            ],
        )
        task_response_metadata = TaskResponseMetadata(
            task_responsed_block=task_response_log["args"]["taskResponseMetadata"][
                "taskResponsedBlock"
            ],
            hash_of_non_signers=task_response_log["args"]["taskResponseMetadata"][
                "hashOfNonSigners"
            ],
        )
        task_response_data = TaskResponseData(
            task_response=task_response,
            task_response_metadata=task_response_metadata,
            non_signing_operator_pub_keys=non_signing_operator_pub_keys,
        )

        task_index = task_response_log["args"]["taskResponse"]["referenceTaskIndex"]
        self.task_responses[task_index] = task_response_data
        logger.debug(
            f"Processed task response for task {task_index} with number squared: {task_response.number_squared}"
        )
        return task_index

    def call_challenge_module(self, task_index: int) -> Optional[Exception]:
        """Call the challenge module for a given task."""
        if task_index not in self.tasks:
            raise TaskNotFoundError()

        number_to_be_squared = self.tasks[task_index].number_to_be_squared
        answer_in_response = self.task_responses[
            task_index
        ].task_response.number_squared
        true_answer = number_to_be_squared**2

        # Check if the answer in the response submitted by aggregator is correct
        if true_answer != answer_in_response:
            logger.debug(
                "The number squared is not correct",
                extra={"expectedAnswer": true_answer, "gotAnswer": answer_in_response},
            )

            # Raise challenge
            self.raise_challenge(task_index)
            return None
        else:
            logger.debug("The number squared is correct")
            raise NoErrorInTaskResponse()

    def get_non_signing_operator_pub_keys(self, task_response_log) -> List[dict]:
        """Get public keys of non-signing operators."""
        tx = self.eth_http_client.eth.get_transaction(
            task_response_log["transactionHash"]
        )
        input_data = tx.input
        func_obj, func_params = self.task_manager.decode_function_input(input_data)
        non_signer_pubkeys = func_params["nonSignerStakesAndSignature"][
            "nonSignerPubkeys"
        ]
        result = []
        for pubkey in non_signer_pubkeys:
            key_dict = {"X": pubkey["X"], "Y": pubkey["Y"]}
            result.append(key_dict)
        return result

    def raise_challenge(self, task_index: int) -> None:
        """Raise a challenge for a given task."""
        logger.debug("Challenger raising challenge.", extra={"taskIndex": task_index})
        logger.debug("Task", extra={"Task": self.tasks[task_index]})
        logger.debug(
            "TaskResponse",
            extra={"TaskResponse": self.task_responses[task_index].task_response},
        )
        logger.debug(
            "TaskResponseMetadata",
            extra={
                "TaskResponseMetadata": self.task_responses[
                    task_index
                ].task_response_metadata
            },
        )
        logger.debug(
            "NonSigningOperatorPubKeys",
            extra={
                "NonSigningOperatorPubKeys": self.task_responses[
                    task_index
                ].non_signing_operator_pub_keys
            },
        )

        tx = self.task_manager.functions.raiseAndResolveChallenge(
            self.tasks[task_index].to_tuple(),
            self.task_responses[task_index].task_response.to_tuple(),
            self.task_responses[task_index].task_response_metadata.to_tuple(),
            self.task_responses[task_index].non_signing_operator_pub_keys,
        ).build_transaction(
            {
                "from": self.challenger_address,
                "gas": 2000000,
                "gasPrice": self.eth_http_client.to_wei("20", "gwei"),
                "nonce": self.eth_http_client.eth.get_transaction_count(
                    self.challenger_address
                ),
                "chainId": self.eth_http_client.eth.chain_id,
            }
        )
        signed_tx = self.eth_http_client.eth.account.sign_transaction(
            tx, private_key=self.challenger_ecdsa_private_key
        )
        tx_hash = self.eth_http_client.eth.send_raw_transaction(
            signed_tx.raw_transaction
        )
        receipt = self.eth_http_client.eth.wait_for_transaction_receipt(tx_hash)
        logger.debug(
            "Challenge raised",
            extra={"challengeTxHash": receipt["transactionHash"].hex()},
        )

    def __load_ecdsa_key(self):
        """Load the ECDSA private key"""
        ecdsa_key_password = os.environ.get("CHALLENGER_ECDSA_KEY_PASSWORD", "")
        if not ecdsa_key_password:
            logger.warning("CHALLENGER_ECDSA_KEY_PASSWORD not set. using empty string.")

        if not os.path.exists(self.config["ecdsa_private_key_store_path"]):
            logger.error(
                f"ECDSA key file not found at: {self.config['ecdsa_private_key_store_path']}"
            )
            raise KeyLoadError(f"ECDSA key file not found")

        with open(self.config["ecdsa_private_key_store_path"], "r") as f:
            keystore = json.load(f)
        self.challenger_ecdsa_private_key = Account.decrypt(
            keystore, ecdsa_key_password
        ).hex()
        self.challenger_address = Account.from_key(
            self.challenger_ecdsa_private_key
        ).address
        logger.debug(f"Loaded ECDSA key for address: {self.challenger_address}")

    def __load_clients(self):
        """Load the AVS clients."""
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
        self.clients = build_all(cfg, self.challenger_ecdsa_private_key)
        self.avs_registry_reader = self.clients.avs_registry_reader
        self.avs_registry_writer = self.clients.avs_registry_writer
        self.el_reader = self.clients.el_reader
        self.el_writer = self.clients.el_writer
        self.eth_http_client = self.clients.eth_http_client
        logger.debug("Successfully loaded AVS clients")

    def __load_task_manager(self):
        """Load the task manager contract."""
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
        self.task_manager = self.eth_http_client.eth.contract(
            address=task_manager_address, abi=task_manager_abi
        )
        logger.debug(f"Task manager loaded at address: {task_manager_address}")


if __name__ == "__main__":
    dir_path = os.path.dirname(os.path.abspath(__file__))

    challenger_config_path = os.path.join(dir_path, "../config-files/challenger.yaml")
    if not os.path.exists(challenger_config_path):
        logger.error(f"Config file not found at: {challenger_config_path}")
        raise FileNotFoundError(f"Config file not found at: {challenger_config_path}")
    with open(challenger_config_path, "r") as f:
        challenger_config = yaml.load(f, Loader=yaml.BaseLoader)

    avs_config_path = os.path.join(dir_path, "../config-files/avs.yaml")
    if not os.path.exists(avs_config_path):
        logger.error(f"Config file not found at: {avs_config_path}")
        raise FileNotFoundError(f"Config file not found at: {avs_config_path}")
    with open(avs_config_path, "r") as f:
        avs_config = yaml.load(f, Loader=yaml.BaseLoader)

    challenger = Challenger(config={**challenger_config, **avs_config})
    challenger.start(None)
