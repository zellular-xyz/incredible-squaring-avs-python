import os
import time
import json
import logging
from random import randbytes
import requests
import yaml
from web3 import Web3
import eth_abi
from eth_account import Account
from eigensdk.chainio.clients.builder import BuildAllConfig, build_all
from eigensdk.crypto.bls.attestation import KeyPair
from eigensdk._types import Operator

# Constants from Go implementation
AVS_NAME = "incredible-squaring"
SEM_VER = "0.0.1"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define specific error types
class OperatorError(Exception):
    """Base class for all operator errors."""
    pass

class KeyLoadError(OperatorError):
    """Error loading keys."""
    pass

class ClientInitializationError(OperatorError):
    """Error initializing clients."""
    pass

class RegistrationError(OperatorError):
    """Error in operator registration."""
    pass

class TaskProcessingError(OperatorError):
    """Error processing task."""
    pass

class AggregatorCommunicationError(OperatorError):
    """Error communicating with aggregator."""
    pass

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
        
        try:
            self.__load_bls_key()
            self.__load_ecdsa_key()
            self.__load_clients()
            self.__load_task_manager()
            
            if config.get("register_operator_on_startup") == 'true':
                self.register_operator_on_startup()
            
            # operator id can only be loaded after registration
            self.__load_operator_id()
            logger.info("Operator initialized successfully")
        except OperatorError as e:
            logger.error(f"Operator initialization failed: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during operator initialization: {str(e)}")
            raise

    def register_operator_on_startup(self):
        """Register operator with EigenLayer and AVS on startup"""
        logger.info("Registering operator on startup")
        
        try:
            self.register_operator_with_eigenlayer()
            logger.info("Registered operator with eigenlayer")
        except Exception as e:
            # This might only be that the operator was already registered
            logger.error(f"Error registering operator with eigenlayer: {str(e)}")
        
        # Deposit into strategy
        amount = int(1e21)  # 1000 tokens with 18 decimals
        try:
            strategy_addr = self.config.get("token_strategy_addr")
            if not strategy_addr:
                logger.error("Token strategy address not configured")
                raise RegistrationError("Token strategy address not configured")
                
            self.deposit_into_strategy(strategy_addr, amount)
            logger.info(f"Deposited {amount} into strategy {strategy_addr}")
        except Exception as e:
            logger.error(f"Error depositing into strategy: {str(e)}")
            raise
        
        # Register for operator sets
        try:
            self.register_for_operator_sets([0])  # Default to quorum 0
            logger.info("Registered operator with AVS")
        except Exception as e:
            logger.error(f"Error registering operator with AVS: {str(e)}")
            raise
        
        # Set allocation delay
        try:
            self.set_allocation_delay(0)
            logger.info("Set allocation delay to 0")
        except Exception as e:
            logger.error(f"Error setting allocation delay: {str(e)}")
        
        # Modify allocations
        try:
            strategies = [self.config.get("token_strategy_addr")]
            new_magnitudes = [100000000]
            self.modify_allocations(strategies, new_magnitudes, 0)
            logger.info("Modified allocations successfully")
        except Exception as e:
            logger.error(f"Error modifying allocations: {str(e)}")

    def register(self):
        """Register the operator with EigenLayer and the AVS"""
        logger.info("Registering operator")
        operator = Operator(
            address=self.config["operator_address"],
            earnings_receiver_address=self.config["operator_address"],
            delegation_approver_address="0x0000000000000000000000000000000000000000",
            allocation_delay=100,
            staker_opt_out_window_blocks=0,
            metadata_url="",
        )
        self.clients.el_writer.register_as_operator(operator)
        self.clients.avs_registry_writer.register_operator_in_quorum_with_avs_registry_coordinator(
            operator_ecdsa_private_key=self.operator_ecdsa_private_key,
            operator_to_avs_registration_sig_salt=randbytes(32),
            operator_to_avs_registration_sig_expiry=int(time.time()) + 3600,
            bls_key_pair=self.bls_key_pair,
            quorum_numbers=[0],
            socket="Not Needed",
        )
        logger.info("Registration complete")

    def start(self):
        """Start the operator service"""
        logger.info("Starting Operator...")
        
        if not self.operator_id:
            logger.error("Operator ID not loaded, cannot start operator")
            raise OperatorError("Operator not registered properly")
            
        event_filter = self.task_manager.events.NewTaskCreated.create_filter(
            from_block="latest"
        )
        
        logger.info("Listening for new tasks...")
        while True:
            try:
                for event in event_filter.get_new_entries():
                    logger.info(f"New task created: {event}")
                    try:
                        task_response = self.process_task_event(event)
                        signed_response = self.sign_task_response(task_response)
                        self.send_signed_task_response(signed_response)
                    except TaskProcessingError as e:
                        logger.error(f"Error processing task: {str(e)}")
                    except AggregatorCommunicationError as e:
                        logger.error(f"Error communicating with aggregator: {str(e)}")
                    except Exception as e:
                        logger.error(f"Unexpected error handling task: {str(e)}")
                time.sleep(3)
            except Exception as e:
                logger.error(f"Error in event processing loop: {str(e)}")
                time.sleep(5)  # Wait a bit longer on error before retrying

    def process_task_event(self, event):
        """Process a new task event and generate a task response"""
        try:
            logger.info("Processing new task",
                extra={
                    "numberToBeSquared": event["args"]["task"]["numberToBeSquared"],
                    "taskIndex": event["args"]["taskIndex"],
                    "taskCreatedBlock": event["args"]["task"]["taskCreatedBlock"],
                    "quorumNumbers": event["args"]["task"]["quorumNumbers"],
                    "QuorumThresholdPercentage": event["args"]["task"]["quorumThresholdPercentage"],
                }
            )
            
            task_index = event["args"]["taskIndex"]
            number_to_be_squared = event["args"]["task"]["numberToBeSquared"]
            number_squared = number_to_be_squared ** 2
            
            # Optional: Simulate failures if configured
            if self.times_failing > 0:
                import random
                if random.randint(0, 99) < self.times_failing:
                    number_squared = 908243203843
                    logger.info("Operator computed wrong task result")
            
            task_response = {
                "referenceTaskIndex": task_index,
                "numberSquared": number_squared
            }
            
            return task_response
        except Exception as e:
            logger.error(f"Error processing task event: {str(e)}")
            raise TaskProcessingError(f"Failed to process task: {str(e)}")

    def sign_task_response(self, task_response):
        """Sign a task response with the operator's BLS key"""
        try:
            encoded = eth_abi.encode(
                ["uint32", "uint256"], 
                [task_response["referenceTaskIndex"], task_response["numberSquared"]]
            )
            hash_bytes = Web3.keccak(encoded)
            signature = self.bls_key_pair.sign_message(msg_bytes=hash_bytes).to_json()
            
            logger.info(
                f"Signature generated, task id: {task_response['referenceTaskIndex']}, "
                f"number squared: {task_response['numberSquared']}"
            )
            
            signed_response = {
                "taskResponse": task_response,
                "blsSignature": signature,
                "operatorId": self.operator_id.hex() if self.operator_id else None
            }
            
            return signed_response
        except Exception as e:
            logger.error(f"Error signing task response: {str(e)}")
            raise TaskProcessingError(f"Failed to sign task response: {str(e)}")

    def send_signed_task_response(self, signed_response):
        """Send a signed task response to the aggregator"""
        logger.info(f"Submitting task response to aggregator")
        
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
            logger.info(f"Successfully sent task response to aggregator, response: {response.text}")
        except requests.RequestException as e:
            logger.error(f"Failed to send task response to aggregator: {str(e)}")
            raise AggregatorCommunicationError(f"Failed to communicate with aggregator: {str(e)}")
        except Exception as e:
            logger.error(f"Unknown error sending task response: {str(e)}")
            raise

    def register_operator_with_eigenlayer(self):
        """Register the operator with EigenLayer"""
        operator = Operator(
            address=self.config["operator_address"],
            earnings_receiver_address=self.config["operator_address"],
            delegation_approver_address="0x0000000000000000000000000000000000000000",
            allocation_delay=100,
            staker_opt_out_window_blocks=0,
            metadata_url="",
        )
        self.clients.el_writer.register_as_operator(operator)

    def deposit_into_strategy(self, strategy_addr, amount):
        """Deposit tokens into a strategy"""
        try:
            # Get token address for the strategy
            token_addr = self.clients.el_reader.get_strategy_and_underlying_token(strategy_addr)
            
            # Mint tokens to the operator
            erc20_contract = self.web3.eth.contract(
                address=Web3.to_checksum_address(token_addr),
                abi=self.__get_erc20_abi()
            )
            
            tx = erc20_contract.functions.mint(
                self.config["operator_address"], 
                amount
            ).build_transaction({
                'from': self.config["operator_address"],
                'gas': 2000000,
                'gasPrice': self.web3.to_wei('20', 'gwei'),
                'nonce': self.web3.eth.get_transaction_count(self.config["operator_address"]),
            })
            
            signed_tx = self.web3.eth.account.sign_transaction(tx, private_key=self.operator_ecdsa_private_key)
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.raw_transaction)
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            logger.info(f"Successfully minted tokens, txHash: {receipt['transactionHash'].hex()}")
            
            # Deposit into strategy
            self.clients.el_writer.deposit_erc20_into_strategy(strategy_addr, amount)
            logger.info(f"Successfully deposited {amount} into strategy {strategy_addr}")
        except Exception as e:
            logger.error(f"Error in deposit_into_strategy: {str(e)}")
            raise

    def register_for_operator_sets(self, operator_set_ids):
        """Register the operator for operator sets"""
        self.clients.avs_registry_writer.register_operator_in_quorum_with_avs_registry_coordinator(
            operator_ecdsa_private_key=self.operator_ecdsa_private_key,
            operator_to_avs_registration_sig_salt=randbytes(32),
            operator_to_avs_registration_sig_expiry=int(time.time()) + 3600,
            bls_key_pair=self.bls_key_pair,
            quorum_numbers=operator_set_ids,
            socket="Not Needed",
        )

    def modify_allocations(self, strategies, new_magnitudes, operator_set_id):
        """Modify allocations for the operator"""
        if not hasattr(self.clients, 'allocation_writer'):
            logger.error("Allocation writer not available")
            return
            
        avs_service_manager = self.config.get("service_manager_address")
        if not avs_service_manager:
            logger.error("Service manager address not configured")
            return
            
        self.clients.allocation_writer.modify_allocations(
            Web3.to_checksum_address(self.config["operator_address"]),
            avs_service_manager,
            operator_set_id,
            strategies,
            new_magnitudes
        )

    def set_allocation_delay(self, delay):
        """Set allocation delay for the operator"""
        if not hasattr(self.clients, 'allocation_writer'):
            logger.error("Allocation writer not available")
            return
            
        self.clients.allocation_writer.set_allocation_delay(
            Web3.to_checksum_address(self.config["operator_address"]),
            delay
        )

    def create_total_delegated_stake_quorum(self, max_operator_count=100, kick_bips_operator_stake=100, 
                                            kick_bips_total_stake=100, minimum_stake=1000000, multiplier=1):
        """Create a total delegated stake quorum"""
        # This is not typically called by the operator directly, but included for completeness
        if not hasattr(self.clients, 'avs_registry_writer'):
            logger.error("AVS registry writer not available")
            return
            
        self.clients.avs_registry_writer.create_total_delegated_stake_quorum(
            max_operator_count,
            kick_bips_operator_stake,
            kick_bips_total_stake,
            minimum_stake,
            [{"strategy": self.config.get("token_strategy_addr"), "multiplier": multiplier}]
        )
    
    def print_operator_status(self):
        """Print the status of the operator"""
        status = {
            "ecdsa_address": self.config["operator_address"],
            "pubkeys_registered": self.operator_id is not None,
            "g1_pubkey": self.bls_key_pair.pub_g1.getStr() if self.bls_key_pair else None,
            "g2_pubkey": self.bls_key_pair.pub_g2.getStr() if self.bls_key_pair else None,
            "registered_with_avs": self.operator_id is not None,
            "operator_id": self.operator_id.hex() if self.operator_id else None
        }
        logger.info(f"Operator status: {json.dumps(status, indent=2)}")
        return status

    def set_appointee(self):
        """Set appointee for the operator - not typically needed for normal operation"""
        pass
        
    def __load_bls_key(self):
        """Load the BLS key pair"""
        try:
            bls_key_password = os.environ.get("OPERATOR_BLS_KEY_PASSWORD", "")
            if not bls_key_password:
                logger.warning("OPERATOR_BLS_KEY_PASSWORD not set. using empty string.")

            if not os.path.exists(self.config["bls_private_key_store_path"]):
                logger.error(f"BLS key file not found at: {self.config['bls_private_key_store_path']}")
                raise KeyLoadError(f"BLS key file not found")

            self.bls_key_pair = KeyPair.read_from_file(
                self.config["bls_private_key_store_path"], bls_key_password
            )
            logger.info(f"BLS PubG1: {self.bls_key_pair.pub_g1.getStr()} PubG2: {self.bls_key_pair.pub_g2.getStr()}")
        except Exception as e:
            logger.error(f"Failed to load BLS key: {str(e)}")
            raise KeyLoadError(f"Failed to load BLS key: {str(e)}")

    def __load_ecdsa_key(self):
        """Load the ECDSA private key"""
        try:
            ecdsa_key_password = os.environ.get("OPERATOR_ECDSA_KEY_PASSWORD", "")
            if not ecdsa_key_password:
                logger.warning("OPERATOR_ECDSA_KEY_PASSWORD not set. using empty string.")

            if not os.path.exists(self.config["ecdsa_private_key_store_path"]):
                logger.error(f"ECDSA key file not found at: {self.config['ecdsa_private_key_store_path']}")
                raise KeyLoadError(f"ECDSA key file not found")

            with open(self.config["ecdsa_private_key_store_path"], "r") as f:
                keystore = json.load(f)
            self.operator_ecdsa_private_key = Account.decrypt(keystore, ecdsa_key_password).hex()
            self.operator_address = Account.from_key(self.operator_ecdsa_private_key).address
            logger.info(f"Loaded ECDSA key for address: {self.operator_address}")
        except Exception as e:
            logger.error(f"Failed to load ECDSA key: {str(e)}")
            raise KeyLoadError(f"Failed to load ECDSA key: {str(e)}")

    def __load_clients(self):
        """Load the AVS clients"""
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
                prom_metrics_ip_port_address="",
            )
            self.clients = build_all(cfg, self.operator_ecdsa_private_key)
            self.web3 = Web3(Web3.HTTPProvider(self.config["eth_rpc_url"]))
            logger.info("Successfully loaded AVS clients")
        except Exception as e:
            logger.error(f"Failed to load AVS clients: {str(e)}")
            raise ClientInitializationError(f"Failed to load AVS clients: {str(e)}")

    def __load_task_manager(self):
        """Load the task manager contract"""
        try:
            service_manager_address = self.clients.avs_registry_writer.service_manager_addr
            
            service_manager_abi_path = "abis/IncredibleSquaringServiceManager.json"
            if not os.path.exists(service_manager_abi_path):
                logger.error(f"Service manager ABI file not found at: {service_manager_abi_path}")
                raise ClientInitializationError(f"Service manager ABI file not found")
                
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
                raise ClientInitializationError(f"Task manager ABI file not found")
                
            with open(task_manager_abi_path) as f:
                task_manager_abi = f.read()
                
            self.task_manager = self.web3.eth.contract(address=task_manager_address, abi=task_manager_abi)
            logger.info(f"Task manager loaded at address: {task_manager_address}")
        except Exception as e:
            logger.error(f"Failed to load task manager: {str(e)}")
            raise ClientInitializationError(f"Failed to load task manager: {str(e)}")

    def __load_operator_id(self):
        """Load the operator ID"""
        try:
            self.operator_id = self.clients.avs_registry_reader.get_operator_id(
                self.config["operator_address"]
            )
            logger.info(f"Loaded operator ID: {self.operator_id.hex() if self.operator_id else None}")
        except Exception as e:
            logger.error(f"Failed to load operator ID: {str(e)}")
            self.operator_id = None

    def __get_erc20_abi(self):
        """Get the ERC20 ABI for interacting with tokens"""
        # Simplified ABI with just the mint function
        return [
            {
                "inputs": [
                    {"internalType": "address", "name": "to", "type": "address"},
                    {"internalType": "uint256", "name": "amount", "type": "uint256"}
                ],
                "name": "mint",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            }
        ]

if __name__ == "__main__":
    try:
        config_path = "config-files/operator.anvil.yaml"
        if not os.path.exists(config_path):
            logger.error(f"Config file not found at: {config_path}")
            raise FileNotFoundError(f"Config file not found at: {config_path}")
            
        with open(config_path, "r") as f:
            config = yaml.load(f, Loader=yaml.BaseLoader)

        operator = SquaringOperator(config=config)
        operator.start()
    except Exception as e:
        logger.critical(f"Failed to start operator: {str(e)}")

    