# Incredible Squaring AVS (Python Edition)

> **Do not use in production. Testnet only.**

A Python-based implementation of the Incredible Squaring AVS middleware with full integration into EigenLayer. This repository showcases how to build and run an Actively Validated Service (AVS) using smart contracts and Python SDK clients for aggregation, operator interaction, and challenge validation.

---

## Dependencies

* Python 3.12+
* [Foundry](https://book.getfoundry.sh/getting-started/installation) for compiling and deploying contracts
* `pip` dependencies (see `requirements.txt`)

Install Foundry:

```bash
curl -L https://foundry.paradigm.xyz | bash
foundryup
```

Build contracts:

```bash
make build-contracts
```

Install Python dependencies:

```bash
pip install -r requirements.txt
```

---

## Running the Project

### 1. Start Local Testnet (Anvil)

```bash
anvil
```

### 2. Deploy Contracts & Setup AVS

```bash
make deploy-all
```

### 3. Run Aggregator (Python version)

```bash
make start-aggregator
```

### 4. Run Operator (Python version)

```bash
make start-operator
```

> The operator will register itself automatically by default. To disable this, set `register_operator_on_startup: false` in the config.

### 5. Run Challenger (Optional, to test slashing)

```bash
make start-challenger
```

---

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

---

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