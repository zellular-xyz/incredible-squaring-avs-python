#!/usr/bin/env python3
import argparse
import logging
import sys
import yaml
from squaring_operator import SquaringOperator
from web3 import Web3

logger = logging.getLogger(__name__)


def register_with_avs(config_path):
    with open(config_path) as f:
        config = yaml.load(f, Loader=yaml.SafeLoader)
    operator = SquaringOperator(config=config)
    operator.set_appointee(
        account_address=config["operator_address"],
        appointee_address=config["operator_address"],
        target=config["service_manager_address"],
        selector="0x00000000",
    )
    operator_set_params = (10, 10000, 2000)
    minimum_stake_required = 1000000
    strategy_addr = Web3.to_checksum_address(config["token_strategy_addr"])
    strategy_params = [(strategy_addr, 10000)]
    receipt = operator.create_total_delegated_stake_quorum(
        operator_set_params, minimum_stake_required, strategy_params
    )
    if receipt.status != 1:
        logger.error(f"Failed to create total delegated stake quorum: {receipt.status}")
        return False
    operator.register_for_operator_sets([0])
    operator.print_operator_status()
    logger.info("Successfully registered operator with AVS")
    return True


def deregister_from_avs(config_path):
    with open(config_path) as f:
        config = yaml.load(f, Loader=yaml.SafeLoader)
    operator = SquaringOperator(config=config)
    receipt = operator.deregister_from_operator_sets([0])
    if receipt.status != 1:
        logger.error(f"Failed to register operator with EigenLayer: {receipt.status}")
        return False
    logger.info("Successfully registered operator with EigenLayer")
    return True


def register_with_eigenlayer(config_path):
    with open(config_path) as f:
        config = yaml.load(f, Loader=yaml.SafeLoader)
    operator = SquaringOperator(config=config)
    receipt = operator.register_operator_with_eigenlayer()
    if receipt.status != 1:
        logger.error(f"Failed to register operator with EigenLayer: {receipt.status}")
        return False
    logger.info("Successfully registered operator with EigenLayer")
    return True


def deposit_into_strategy(config_path):
    with open(config_path) as f:
        config = yaml.load(f, Loader=yaml.SafeLoader)
    operator = SquaringOperator(config=config)
    operator.deposit_into_strategy(config["token_strategy_addr"], 1000000000000000000)
    logger.info(
        f"Successfully deposited 1000000000000000000 into strategy {config['token_strategy_addr']}"
    )
    return True


def main():
    parser = argparse.ArgumentParser(description="Incredible Squaring AVS CLI")
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Log level",
    )

    subparsers = parser.add_subparsers(dest="command")

    # Define commands with their handlers
    commands = {
        "register-with-eigenlayer": register_with_eigenlayer,
        "register-with-avs": register_with_avs,
        "deregister-from-avs": deregister_from_avs,
        "deposit": deposit_into_strategy,
    }

    # Add parsers for each command
    for cmd, _ in commands.items():
        cmd_parser = subparsers.add_parser(cmd)
        cmd_parser.add_argument(
            "--config", type=str, default="config-files/operator.anvil.yaml"
        )

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    if not args.command:
        parser.print_help()
        sys.exit(1)

    config_path = args.config

    if args.command == "register-with-eigenlayer":
        success = register_with_eigenlayer(config_path=config_path)
    elif args.command == "register-with-avs":
        success = register_with_avs(config_path=config_path)
    elif args.command == "deregister-from-avs":
        success = deregister_from_avs(config_path=config_path)
    elif args.command == "deposit":
        success = deposit_into_strategy(config_path=config_path)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
