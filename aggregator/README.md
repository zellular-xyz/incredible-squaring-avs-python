# Incredible Squaring AVS Aggregator

This aggregator is a core component of the Incredible Squaring Actively Validated Service (AVS) built on EigenLayer. It orchestrates the process of creating tasks, collecting operator responses, and submitting aggregated results to the blockchain.

## Overview

The Incredible Squaring AVS aggregator performs the following key functions:

1. **Task Creation**: Periodically creates new tasks (numbers to be squared) and submits them to the task manager contract
2. **Response Collection**: Receives signed responses from registered operators via HTTP API
3. **Signature Verification**: Validates BLS signatures from operators using their registered public keys
4. **Response Aggregation**: Aggregates operator responses when sufficient stake threshold is reached
5. **On-chain Submission**: Submits aggregated responses to the blockchain contract

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Operators     │────│   Aggregator     │────│  Blockchain     │
│                 │    │                  │    │                 │
│ - Sign responses│    │ - Create tasks   │    │ - Task Manager  │
│ - Submit sigs   │    │ - Verify sigs    │    │ - Service Mgr   │
│                 │    │ - Aggregate      │    │ - AVS Registry  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                       ┌──────────────┐
                       │   Subgraph   │
                       │              │
                       │ - Query ops  │
                       │ - Get stakes │
                       └──────────────┘
```

## Features

- **Automatic Task Generation**: Sends new squaring tasks every 10 seconds
- **Signature Verification**: Validates operator signatures using BLS cryptography
- **Stake-Weighted Aggregation**: Considers operator stake when determining consensus
- **Threshold Management**: Configurable threshold percentage for task completion
- **REST API**: HTTP endpoint for operators to submit signatures
- **Error Handling**: Comprehensive error handling with specific error types
- **Logging**: Detailed logging for monitoring and debugging

## Prerequisites

- Python 3.8+
- Access to Ethereum RPC endpoint
- EigenLayer AVS contracts deployed
- Subgraph endpoint for operator data
- ECDSA private key for aggregator

## Installation

1. **Install Dependencies**:
```bash
pip install -r requirements.txt
```

2. **Set up Configuration**:
Create `config-files/aggregator.yaml` with the following structure:
```yaml
eth_rpc_url: "http://localhost:8545"
aggregator_server_ip_port_address: "localhost:8080"
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
export AGGREGATOR_ECDSA_KEY_PASSWORD="your_keystore_password"
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
| `aggregator_server_ip_port_address` | IP:port for the HTTP server |
| `ecdsa_private_key_store_path` | Path to aggregator's encrypted keystore |
| `avs_registry_coordinator_address` | AVS registry coordinator contract address |
| `operator_state_retriever_address` | Operator state retriever contract address |
| `service_manager_address` | Service manager contract address |

### Constants

- `TASK_CHALLENGE_WINDOW_BLOCK`: 100 blocks
- `BLOCK_TIME_SECONDS`: 12 seconds
- `THRESHOLD_PERCENT`: 70% stake threshold
- `AVS_NAME`: "incredible-squaring"

## Usage

### Starting the Aggregator

```bash
python aggregator.py
```

The aggregator will:
1. Start the HTTP server for receiving operator signatures
2. Begin sending new tasks every 10 seconds
3. Process incoming signatures and aggregate responses

### API Endpoints

#### POST /signature
Accepts operator signature submissions.

**Request Body**:
```json
{
    "task_index": 0,
    "operator_id": "0x1234...",
    "number_squared": 25,
    "block_number": 1000,
    "signature": {
        "X": "0x...",
        "Y": "0x..."
    }
}
```

**Response**:
- `200`: Signature accepted
- `400`: Various errors (task not found, operator not registered, etc.)
- `500`: Internal server error

## Error Types

The aggregator defines specific error types for better error handling:

- `TaskNotFoundError`: Task not found in aggregator state
- `OperatorNotRegisteredError`: Operator not registered in the AVS
- `OperatorAlreadyProcessedError`: Duplicate signature from same operator
- `SignatureVerificationError`: BLS signature verification failed
- `InternalServerError`: Unexpected server errors

## Logging

The aggregator uses Python's logging module with INFO level by default. Key events logged include:

- Task creation and submission
- Signature verification results
- Aggregation progress
- Error conditions

To enable debug logging, modify the logging level:
```python
logging.basicConfig(level=logging.DEBUG)
```

## Monitoring

The aggregator includes Prometheus metrics support. Configure the metrics endpoint in your config file:
```yaml
prom_metrics_ip_port_address: "localhost:9090"
```

## Security Considerations

1. **Private Key Security**: Store ECDSA private keys securely using encrypted keystores
2. **Environment Variables**: Use environment variables for sensitive data like passwords
3. **Network Security**: Ensure RPC endpoints and subgraph are properly secured
4. **Input Validation**: The aggregator validates all operator signatures before processing

## Troubleshooting

### Common Issues

1. **Connection Errors**: Verify RPC URL and network connectivity
2. **Signature Verification Failures**: Check operator registration and key formats
3. **Transaction Failures**: Ensure sufficient gas and correct nonce handling
4. **Subgraph Errors**: Verify subgraph endpoint availability

### Debug Mode

Enable debug logging for detailed execution traces:
```python
logging.basicConfig(level=logging.DEBUG)
```

## Development

### Running Tests
```bash
python -m pytest tests/
```

### Code Structure

- `Aggregator.__init__()`: Initialize clients and configuration
- `send_new_task()`: Create and submit new tasks
- `submit_signature()`: Handle operator signature submissions
- `__verify_signature()`: Verify BLS signatures
- `__submit_aggregated_response()`: Submit to blockchain

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For questions and support:
- Open an issue on GitHub
- Check the EigenLayer documentation
- Review the AVS developer guides 