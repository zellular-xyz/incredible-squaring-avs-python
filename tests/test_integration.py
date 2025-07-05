import logging
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
import json

import yaml

from tests.mocks import MockAggregator

sys.path.append(str(Path(__file__).resolve().parent.parent))

from squaring_operator import SquaringOperator  # noqa: E402
from challenger import Challenger  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def start_anvil_and_deploy_contracts():
    """start anvil and deploy contracts"""
    anvil_process = subprocess.Popen(
        [
            "anvil",
            "--load-state",
            "tests/anvil/avs-and-eigenlayer-deployed-anvil-state/state.json",
            "--print-traces",
            "-vvvvv",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return anvil_process


def start_operator(number):
    """start operator"""
    dir_path = os.path.dirname(os.path.abspath(__file__))

    operator_config_path = os.path.join(
        dir_path, f"../config-files/operator{number}.yaml"
    )
    if not os.path.exists(operator_config_path):
        logger.error(f"Config file not found at: {operator_config_path}")
        raise FileNotFoundError(f"Config file not found at: {operator_config_path}")
    with open(operator_config_path, "r") as f:
        operator_config = yaml.load(f, Loader=yaml.BaseLoader)

    avs_config_path = os.path.join(dir_path, "../config-files/avs.yaml")
    if not os.path.exists(avs_config_path):
        logger.error(f"Config file not found at: {avs_config_path}")
        raise FileNotFoundError(f"Config file not found at: {avs_config_path}")
    with open(avs_config_path, "r") as f:
        avs_config = yaml.load(f, Loader=yaml.BaseLoader)

    operator = SquaringOperator(config={**operator_config, **avs_config})
    operator_thread = threading.Thread(target=operator.start, daemon=True)
    operator_thread.start()
    return operator, operator_thread


def start_aggregator():
    """start aggregator"""
    dir_path = os.path.dirname(os.path.abspath(__file__))

    aggregator_config_path = os.path.join(dir_path, "../config-files/aggregator.yaml")
    if not os.path.exists(aggregator_config_path):
        logger.error(f"Config file not found at: {aggregator_config_path}")
        raise FileNotFoundError(f"Config file not found at: {aggregator_config_path}")
    with open(aggregator_config_path, "r") as f:
        aggregator_config = yaml.load(f, Loader=yaml.BaseLoader)

    avs_config_path = os.path.join(dir_path, "../config-files/avs.yaml")
    if not os.path.exists(avs_config_path):
        logger.error(f"Config file not found at: {avs_config_path}")
        raise FileNotFoundError(f"Config file not found at: {avs_config_path}")
    with open(avs_config_path, "r") as f:
        avs_config = yaml.load(f, Loader=yaml.BaseLoader)

    aggregator = MockAggregator(config={**aggregator_config, **avs_config})
    aggregator_thread = threading.Thread(target=aggregator.start, daemon=True)
    aggregator_thread.start()
    return aggregator, aggregator_thread

def start_challenger():
    """start challenger"""
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
    challenger_thread = threading.Thread(target=challenger.start, daemon=True)
    challenger_thread.start()
    return challenger, challenger_thread


import time
import json

def test_incredible_squaring_e2e():
    print("Starting anvil")
    anvil_process = start_anvil_and_deploy_contracts()
    print("Anvil started")

    print("Starting operators")
    operators = []
    threads = []
    for i in range(1, 4):
        operator, thread = start_operator(i)
        operators.append(operator)
        threads.append(thread)
    print("Operators started")

    print("Starting aggregator")
    aggregator, aggregator_thread = start_aggregator()
    print("Aggregator started")

    print("Starting challenger")
    challenger, challenger_thread = start_challenger()
    print("Challenger started")

    try:
        print("Waiting for 10 seconds...")
        time.sleep(10)

        print("\nChecking task manager")
        task_manager = aggregator.task_manager
        task_hash = task_manager.functions.allTaskHashes(0).call()
        task_response_hash = task_manager.functions.allTaskResponses(0).call()

        print("Task hash:", task_hash)
        print("Task response hash:", task_response_hash)

        empty_bytes = b"\x00" * 32
        assert task_hash != empty_bytes, "Task hash is empty"
        assert task_response_hash != empty_bytes, "Task response hash is empty"

        print("\nRetrieving task and response from challenger")
        task = challenger.tasks.get(0)
        task_response = challenger.task_responses.get(0)
        challenge_hash = challenger.challenge_hashes.get(0)

        assert task is not None, "Task not found in challenger"
        assert task_response is not None, "Task response not found in challenger"

        print("\nTask:")
        print(json.dumps(task.to_json(), indent=2))

        print("\nTask Response:")
        print(json.dumps(task_response.to_json(), indent=2))

        # Validate squaring logic
        correct_result = task.number_to_be_squared ** 2
        actual_result = task_response.task_response.number_squared
        is_response_wrong = actual_result != correct_result

        # Verify challenge state
        if is_response_wrong and challenge_hash is None:
            raise AssertionError("Response is wrong, but no challenge was raised")
        elif not is_response_wrong and challenge_hash is not None:
            raise AssertionError("Response is correct, but a challenge was raised")

        # Output summary
        print("\n================================================")
        print(f"Task: square {task.number_to_be_squared} (block {task.task_created_block})")
        print(f"Response: {actual_result} (block {task_response.task_response_metadata.task_responsed_block})")
        if is_response_wrong:
            print(f"Response was incorrect. Challenge raised: {challenge_hash}")
        else:
            print("Response was correct. No challenge raised.")
        print("PASSED")
        print("================================================")

    finally:
        print("\nCleaning up processes...")
        for operator in operators:
            operator.stop()
        aggregator.stop()
        challenger.stop()

        for thread in threads:
            thread.join()
        aggregator_thread.join()
        challenger_thread.join()
        anvil_process.terminate()
        print("Cleanup complete")
