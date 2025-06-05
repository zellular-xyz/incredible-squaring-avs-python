import logging
import os
import subprocess
import threading
import time

import yaml

from operator.squaring_operator import SquaringOperator
from tests.mocks import MockAggregator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def start_anvil_and_deploy_contracts():
    """start anvil and deploy contracts"""
    anvil_process = subprocess.Popen(
        ["anvil"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    time.sleep(1)
    subprocess.run(
        ["make", "deploy-all"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    return anvil_process


def start_operator():
    """start operator"""
    config_path = "config-files/operator.anvil.yaml"
    if not os.path.exists(config_path):
        logger.error(f"Config file not found at: {config_path}")
        raise FileNotFoundError(f"Config file not found at: {config_path}")

    with open(config_path, "r") as f:
        config = yaml.load(f, Loader=yaml.BaseLoader)

    operator = SquaringOperator(config=config)
    operator_thread = threading.Thread(target=operator.start)
    operator_thread.start()
    return operator, operator_thread


def start_aggregator():
    """start aggregator"""
    with open("config-files/aggregator.yaml", "r") as f:
        config = yaml.load(f, Loader=yaml.BaseLoader)
    aggregator = MockAggregator(config)
    aggregator_thread = threading.Thread(target=aggregator.start)
    aggregator_thread.start()
    return aggregator, aggregator_thread


if __name__ == "__main__":
    print("Starting anvil and deploying contracts")
    anvil_process = start_anvil_and_deploy_contracts()
    print("anvil started and contracts deployed")
    print("Starting operator")
    operator, operator_thread = start_operator()
    print("operator started")
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
    operator.stop()
    aggregator.stop()
    operator_thread.join()
    anvil_process.terminate()
    print("Cleanup complete")
    pid = os.getpid()
    os.kill(pid, 9)
