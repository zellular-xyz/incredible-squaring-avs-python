# Incredible Squaring AVS Challenger

The challenger is a critical component of the Incredible Squaring Actively Validated Service (AVS) built on EigenLayer. It monitors task responses submitted by the aggregator and raises challenges when incorrect responses are detected, ensuring the integrity of the AVS.

## Overview

The Incredible Squaring AVS challenger performs the following key functions:

1. **Event Monitoring**: Listens for `NewTaskCreated` and `TaskResponded` events from the blockchain
2. **Response Validation**: Verifies that aggregated responses contain correct calculations (number squared correctly)
3. **Challenge Detection**: Identifies incorrect responses by comparing expected vs actual results
4. **Challenge Submission**: Raises on-chain challenges for incorrect responses
5. **Fraud Prevention**: Protects the AVS from malicious or incorrect aggregator behavior

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Blockchain    │────│   Challenger     │────│  Task Manager   │
│                 │    │                  │    │                 │
│ - Events        │    │ - Monitor tasks  │    │ - Challenge     │
│ - Task creation │    │ - Validate resp  │    │ - Resolution    │
│ - Task response │    │ - Raise dispute  │    │ - Slashing      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                       ┌──────────────┐
                       │ AVS Registry │
                       │              │
                       │ - Operators  │
                       │ - Stakes     │
                       └──────────────┘
```

## Features

- **Real-time Monitoring**: Continuously monitors blockchain events for new tasks and responses
- **Automatic Validation**: Automatically validates mathematical correctness of responses
- **Challenge Mechanism**: Raises challenges for incorrect responses with full proof data
- **Event-driven Architecture**: Efficient event-based processing with minimal resource usage
- **Error Handling**: Comprehensive error handling for various failure scenarios
- **Fraud Detection**: Protects against aggregator misbehavior and calculation errors

## Data Structures

### Task
Represents a task created by the aggregator:
```python
@dataclass
class Task:
    number_to_be_squared: int
    task_created_block: int
    quorum_numbers: bytes
    quorum_threshold_percentage: int
```

### TaskResponse
Represents the response submitted for a task:
```python
@dataclass
class TaskResponse:
    number_squared: int
    reference_task_index: int
```

### TaskResponseMetadata
Contains metadata about the task response:
```python
@dataclass
class TaskResponseMetadata:
    task_responsed_block: int
    hash_of_non_signers: bytes
```

## Prerequisites

- Python 3.8+
- Access to Ethereum RPC endpoint
- EigenLayer AVS contracts deployed
- ECDSA private key for challenger
- Access to task manager contract ABIs

## Installation

1. **Install Dependencies**:
```bash
pip install -r requirements.txt
```

2. **Set up Configuration**:
Create `config-files/challenger.yaml` with the following structure:
```yaml
eth_rpc_url: "http://localhost:8545"
ecdsa_private_key_store_path: "path/to/keystore.json"
avs_registry_coordinator_address: "0x..."
operator_state_retriever_address: "0x..."
rewards_coordinator_address: "0x..."
permission_controller_address: "0x..."
service_manager_address: "0x..."
allocation_manager_address: "0x..."
instant_slasher_address: "0x..."
delegation_manager_address: "0x..."
prom_metrics_ip_port_address: "localhost:9090"
```

3. **Set Environment Variables**:
```bash
export CHALLENGER_ECDSA_KEY_PASSWORD="your_keystore_password"
```

4. **Prepare Contract ABIs**:
Ensure the following ABI files are available:
- `abis/IncredibleSquaringServiceManager.json`
- `abis/IncredibleSquaringTaskManager.json`

## Configuration

### Required Configuration Parameters

| Parameter | Description |
|-----------|-------------|
| `eth_rpc_url` | Ethereum RPC endpoint URL |
| `ecdsa_private_key_store_path` | Path to challenger's encrypted keystore |
| `avs_registry_coordinator_address` | AVS registry coordinator contract address |
| `operator_state_retriever_address` | Operator state retriever contract address |
| `service_manager_address` | Service manager contract address |

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `CHALLENGER_ECDSA_KEY_PASSWORD` | Password for encrypted keystore | No (defaults to empty) |

## Usage

### Starting the Challenger

```bash
python challenger.py
```

The challenger will:
1. Load configuration and initialize blockchain clients
2. Set up event filters for task creation and response events
3. Begin monitoring blockchain events in real-time
4. Automatically validate responses and raise challenges when needed

### Challenge Process

1. **Event Detection**: Challenger detects a new task or task response event
2. **Data Collection**: Extracts task details and response data
3. **Validation**: Compares expected result (number²) with submitted response
4. **Challenge Decision**: If incorrect, prepares challenge transaction
5. **Challenge Submission**: Submits `raiseAndResolveChallenge` transaction to contract

### Example Challenge Flow

```
Task Created: Square 5
├── Expected Result: 25
├── Aggregator Response: 24 (incorrect)
├── Challenger Validation: 5² = 25 ≠ 24
└── Challenge Raised: Transaction submitted to blockchain
```

## Error Types

The challenger defines specific error types for different scenarios:

- `KeyLoadError`: Failed to load ECDSA private key
- `TaskNotFoundError`: Referenced task not found in challenger state
- `TransactionError`: Failed to execute blockchain transaction
- `TaskResponseParsingError`: Failed to parse task response data
- `NoErrorInTaskResponse`: Task response is correct (not an error)

## Event Processing

### NewTaskCreated Events
- Extracts task index and task details
- Stores task information for future reference
- Checks if corresponding response already exists

### TaskResponded Events
- Extracts response data and metadata
- Retrieves non-signing operator public keys
- Validates response correctness
- Raises challenge if response is incorrect

## Monitoring and Logging

The challenger uses Python's logging module with INFO level by default. Key events logged include:

- New task detection and processing
- Task response validation results
- Challenge raising activities
- Error conditions and failures

### Enable Debug Logging
```python
logging.basicConfig(level=logging.DEBUG)
```

### Log Examples
```
DEBUG:challenger:New task created log received taskIndex=5 task={...}
DEBUG:challenger:Task response log received taskResponse={...}
DEBUG:challenger:The number squared is not correct expectedAnswer=25 gotAnswer=24
DEBUG:challenger:Challenge raised challengeTxHash=0x...
```

## Security Considerations

1. **Private Key Security**: Store ECDSA private keys securely using encrypted keystores
2. **Network Security**: Ensure RPC endpoints are properly secured and authenticated
3. **Gas Management**: Monitor gas costs for challenge transactions
4. **Event Reliability**: Handle potential event loss or reorg scenarios
5. **False Positives**: Ensure validation logic correctly handles edge cases

## Gas and Transaction Management

- **Gas Limit**: Default 2,000,000 gas for challenge transactions
- **Gas Price**: Default 20 gwei (configurable)
- **Nonce Management**: Automatic nonce tracking for transaction sequencing
- **Transaction Waiting**: Waits for transaction confirmation before logging success

## Troubleshooting

### Common Issues

1. **Key Loading Failures**:
   - Verify keystore file exists and is properly formatted
   - Check ECDSA password environment variable

2. **Event Processing Errors**:
   - Verify RPC endpoint connectivity and permissions
   - Check contract addresses in configuration

3. **Transaction Failures**:
   - Ensure sufficient ETH balance for gas fees
   - Verify contract ABIs are correct and up-to-date

4. **Challenge Failures**:
   - Check task manager contract permissions
   - Verify challenge window hasn't expired

### Debug Commands

Check challenger address and balance:
```bash
# View challenger address from logs
grep "Loaded ECDSA key" challenger.log

# Check ETH balance
curl -X POST -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"eth_getBalance","params":["0xYourAddress","latest"],"id":1}' \
  http://localhost:8545
```

## Development

### Running Tests
```bash
python -m pytest tests/test_challenger.py -v
```

### Code Structure

- `Challenger.__init__()`: Initialize configuration, keys, and clients
- `start()`: Main event processing loop
- `process_new_task_created_log()`: Handle new task events
- `process_task_response_log()`: Handle task response events
- `call_challenge_module()`: Validate responses and determine if challenge needed
- `raise_challenge()`: Submit challenge transaction to blockchain

### Adding Custom Validation

To add custom validation logic:

1. Modify `call_challenge_module()` method
2. Implement additional validation checks
3. Ensure proper error handling for new scenarios

## Performance Considerations

- **Event Polling**: Default 3-second interval between event checks
- **Memory Usage**: Stores tasks and responses in memory (consider cleanup for long-running instances)
- **Network Calls**: Minimizes RPC calls by using event filters
- **Concurrent Processing**: Single-threaded design for simplicity and reliability

## Contributing

1. Fork the repository
2. Create a feature branch
3. Implement changes with appropriate tests
4. Ensure logging and error handling are maintained
5. Submit a pull request with detailed description

## Integration with AVS Ecosystem

The challenger integrates with several components:

- **Task Manager Contract**: Monitors events and submits challenges
- **Service Manager**: Retrieves contract addresses and configurations
- **AVS Registry**: Validates operator information and stakes
- **EigenLayer Core**: Leverages slashing and delegation mechanisms

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For questions and support:
- Open an issue on GitHub
- Check the EigenLayer documentation
- Review the AVS developer guides
- Join the EigenLayer Discord community 