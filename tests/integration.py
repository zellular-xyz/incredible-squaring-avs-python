import logging
import os
import subprocess
import threading
import time

import yaml

from squaring_operator.squaring_operator import SquaringOperator
from tests.mocks import MockAggregator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def start_anvil_and_deploy_contracts():
    """start anvil and deploy contracts"""
    anvil_process = subprocess.Popen(
        ["anvil", "--load-state", "contracts/state.json", "--print-traces", "-vvvvv"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    return anvil_process


def start_operator(number):
    """start operator"""
    dir_path = os.path.dirname(os.path.abspath(__file__))

    operator_config_path = os.path.join(dir_path, f"../config-files/operator{number}.yaml")
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


if __name__ == "__main__":
    print("Starting anvil")
    anvil_process = start_anvil_and_deploy_contracts()
    print("Anvil started")
    print("Starting operators")
    operator1, operator_thread1 = start_operator(1)
    operator2, operator_thread2 = start_operator(2)
    operator3, operator_thread3 = start_operator(3)
    print("operators started")
    print("Starting aggregator")
    aggregator, aggregator_thread = start_aggregator()
    print("aggregator started")
    print("Waiting for 10 seconds")
    time.sleep(10)
    print("Checking task manager")
    task_manager = aggregator.task_manager
    task_hash = task_manager.functions.allTaskHashes(0).call()
    task_response_hash = task_manager.functions.allTaskResponses(0).call()
    print("task_hash", task_hash)
    print("task_response_hash", task_response_hash)
    empty_bytes = b"\x00" * 32
    if not (task_hash != empty_bytes and task_response_hash != empty_bytes):
        print("task_hash or task_response_hash is empty")
        print("FAILED")
    else:
        print("task_hash and task_response_hash are not empty")
        print("PASSED")

    print("Cleaning up processes...")
    operator1.stop()
    operator2.stop()
    operator3.stop()
    aggregator.stop()
    operator_thread1.join()
    operator_thread2.join()
    operator_thread3.join()
    anvil_process.terminate()
    print("Cleanup complete")
    # pid = os.getpid()
    # os.kill(pid, 9)