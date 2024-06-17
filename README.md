# Incredible Squaring AVS in Python

<b> Do not use it in Production, testnet only. </b>

A Python implemention of the EigenLayer [Incredible Squaring AVS](https://github.com/Layr-Labs/incredible-squaring-avs) 

## Dependencies

You will need [foundry](https://book.getfoundry.sh/getting-started/installation) and docker to run the examples below.
```
curl -L https://foundry.paradigm.xyz | bash
foundryup
```

You will also need to [install docker](https://docs.docker.com/get-docker/), and build the contracts:
```
make build-contracts
```

You will also need Python3 and install required modules:
```
pip install -r requirements.txt
```

## Running via make

This simple session illustrates the basic flow of the AVS. The makefile commands are hardcoded for a single operator, but it's however easy to create new operator config files, and start more operators manually (see the actual commands that the makefile calls).

Start anvil in a separate terminal:

```bash
make start-anvil-chain-with-el-and-avs-deployed
```

The above command starts a local anvil chain from a [saved state](./tests/anvil/avs-and-eigenlayer-deployed-anvil-state.json) with eigenlayer and incredible-squaring contracts already deployed (but no operator registered).

Start the aggregator:

```bash
make start-aggregator
```

Register the operator with eigenlayer and incredible-squaring, and then start the process:

```bash
make start-operator
```