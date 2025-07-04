# Incredible Squaring AVS (Python Edition)

<b> Do not use it in Production, testnet only. </b>

An implementation of the EigenLayer [Incredible Squaring AVS](https://github.com/Layr-Labs/incredible-squaring-avs) in Python. This repository showcases how to use [EigenLayer Python SDK](https://github.com/zellular-xyz/eigensdk-python/) to build an Autonomous Verifiable Service (AVS) in Python.

## Dependencies

[Foundry](https://book.getfoundry.sh/getting-started/installation) is required to build the AVS smart contracts, run a local Anvil chain, deploy contracts to Anvil, and test the Python AVS against the local setup.

Install Foundry:

``` bash
curl -L https://foundry.paradigm.xyz | bash
foundryup
```

Python 3.11+ with pip is required to run the AVS binaries.

Node.js 20+ with npm is required to build and deploy the subgraph to a local Graph Node.

[Docker](https://docs.docker.com/get-docker/)  is required to run the Graph Node and IPFS services using Docker Compose, and to run the Docker-based tests.


## Quick Test (using Docker)

```bash
make build-docker
make test-docker
```

## Install

Create a virtual environment and install Python dependencies using:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install .
```

For development (includes linting, type checking, and formatting tools) install the repository using:

```bash
pip install -e ".[dev]"
```

Install latest version of node and required dependencies for deploying subgraph:

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
\. "$HOME/.nvm/nvm.sh"
nvm install 22

cd avs-subgraph
npm i -g @graphprotocol/graph-cli@latest
npm i
```

## Running via make

This simple session illustrates the basic flow of the AVS. The makefile commands are hardcoded for a single operator, but it's however easy to create new operator config files, and start more operators manually (see the actual commands that the makefile calls).

Start anvil in a separate terminal:

```bash
anvil --host 0.0.0.0
```

**Note:** Using `--host 0.0.0.0` enables the subgraph node to connect to the anvil chain.

Build the contracts:

``` bash
make build-contracts
```

Deploy contracts, set UAM permissions, and create a quorum in a single command:

```bash
make deploy-all
```

Start the graph node:

```bash
make start-graph-node
```

**Note:** To start the graph node from scratch, remove the `data` folder inside the `avs-subgraph` using `rm avs-subgraph/data -rf` before starting the subgraph.

Deploy the subgraph:

```bash
make deploy-subgraph
```

Start the aggregator:

```bash
make start-aggregator
```

Register the operator with eigenlayer and incredible-squaring, and then start the process:

```bash
make start-operator
```

By default, the `start-operator` command will also register the operator.
To disable this, set `register_operator_on_startup` to false in `config-files/operator.anvil.yaml`.
The operator can be manually registered by running `make cli-setup-operator`.

The operator will produce an invalid result 10 times out of 100, as it is set in the `times_failing` field of the config.
These failures result in slashing once they're challenged.
To see this in action, start the challenger with:

```bash
make start-challenger
```

## Distribution & Reward Claims

### Equal Distribution:

```bash
make create-avs-distributions-root
make claim-distributions
make claimer-account-token-balance
```

### Operator-Directed Distribution:

```bash
make create-operator-directed-distributions-root
make claim-distributions
make claimer-account-token-balance
```


## Architecture Overview

* **Aggregator:** Publishes new tasks, aggregates signed responses, and submits them on-chain.
* **Operator:** Listens for tasks, computes square, signs result, and submits to aggregator.
* **Challenger:** Verifies correctness of submitted results and challenges if incorrect.

Each task requires computing `x^2` for a given `x`. The aggregator checks that BLS signature quorum thresholds are met before submitting the aggregated result.

---

## Cronjob: Stake Updates

The AVS stake view may become stale. A Python cronjob (TBD) will call `StakeRegistry.updateStakes()` periodically to refresh operator stake information.

---

## Tests

Run integration tests locally:

```bash
pytest tests/ -v
```

## Code Quality

### Linting

Run code linting with flake8:

```bash
make lint
```

### Type Checking

Run type checking with mypy:

```bash
make mypy
```

### Code Formatting

Format code with black and isort:

```bash
make format
```

Check if code is properly formatted:

```bash
make format-check
```

### Run All Checks

Run all code quality checks at once:

```bash
make check-all
```

## Avs Task Description

The architecture of the AVS contains:

- [Eigenlayer core](https://github.com/Layr-Labs/eigenlayer-contracts/tree/master) contracts
- AVS contracts
  - [ServiceManager](contracts/src/IncredibleSquaringServiceManager.sol) which will eventually contain slashing logic but for M2 is just a placeholder.
  - [TaskManager](contracts/src/IncredibleSquaringTaskManager.sol) which contains [task creation](contracts/src/IncredibleSquaringTaskManager.sol#L83) and [task response](contracts/src/IncredibleSquaringTaskManager.sol#L102) logic.
  - The [challenge](contracts/src/IncredibleSquaringTaskManager.sol#L176) logic could be separated into its own contract, but we have decided to include it in the TaskManager for this simple task.
  - Set of [registry contracts](https://github.com/Layr-Labs/eigenlayer-middleware) to manage operators opted in to this avs
- Task Generator
  - in a real world scenario, this could be a separate entity, but for this simple demo, the aggregator also acts as the task generator
- Aggregator
  - aggregates BLS signatures from operators and posts the aggregated response to the task manager
  - For this simple demo, the aggregator is not an operator, and thus does not need to register with eigenlayer or the AVS contract. It's IP address is simply hardcoded into the operators' config.
- Operators
  - Square the number sent to the task manager by the task generator, sign it, and send it to the aggregator

![](./diagrams/architecture.png)

1. A task generator (in our case, same as the aggregator) publishes tasks once every regular interval (say 10 blocks, you are free to set your own interval) to the IncredibleSquaringTaskManager contract's [createNewTask](contracts/src/IncredibleSquaringTaskManager.sol#L83) function. Each task specifies an integer `numberToBeSquared` for which it wants the currently opted-in operators to determine its square `numberToBeSquared^2`. `createNewTask` also takes `quorumNumbers` and `quorumThresholdPercentage` which requests that each listed quorum (we only use quorumNumber 0 in incredible-squaring) needs to reach at least thresholdPercentage of operator signatures.

2. A [registry](https://github.com/Layr-Labs/eigenlayer-middleware/blob/master/src/BLSRegistryCoordinatorWithIndices.sol) contract is deployed that allows any eigenlayer operator with at least 1 delegated [mockerc20](contracts/src/ERC20Mock.sol) token to opt-in to this AVS and also de-register from this AVS.

3. [Operator] The operators who are currently opted-in with the AVS need to read the task number from the Task contract, compute its square, sign on that computed result (over the BN254 curve) and send their taskResponse and signature to the aggregator.

4. [Aggregator] The aggregator collects the signatures from the operators and aggregates them using BLS aggregation. If any response passes the [quorumThresholdPercentage](contracts/src/IIncredibleSquaringTaskManager.sol#L36) set by the task generator when posting the task, the aggregator posts the aggregated response to the Task contract.

5. If a response was sent within the [response window](contracts/src/IncredibleSquaringTaskManager.sol#L119), we enter the [Dispute resolution] period.
   - [Off-chain] A challenge window is launched during which anyone can [raise a dispute](contracts/src/IncredibleSquaringTaskManager.sol#L171) in a DisputeResolution contract (in our case, this is the same as the TaskManager contract)
   - [On-chain] The DisputeResolution contract resolves that a particular operator's response is not the correct response (that is, not the square of the integer specified in the task) or the opted-in operator didn't respond during the response window. If the dispute is resolved, the operator will be frozen in the Registration contract and the veto committee will decide whether to veto the freezing request or not.

Below is a more detailed uml diagram of the aggregator and operator processes:

![](./diagrams/uml.png)

---

## Troubleshooting

**Error:** `task X not initialized or already completed`

This occurs when the operator submits a result before the aggregator has initialized the task. This is expected in local setups. The operator retries after a delay.

---

## References

* AVS Subgraph: [https://github.com/zellular-xyz/avs-subgraph](https://github.com/zellular-xyz/avs-subgraph)
* EigenSDK-Python: [https://github.com/zellular-xyz/eigensdk-python](https://github.com/zellular-xyz/eigensdk-python)
* EigenLayer contracts: [https://github.com/Layr-Labs/eigenlayer-contracts](https://github.com/Layr-Labs/eigenlayer-contracts)
* Middleware registry: [https://github.com/Layr-Labs/eigenlayer-middleware](https://github.com/Layr-Labs/eigenlayer-middleware)

