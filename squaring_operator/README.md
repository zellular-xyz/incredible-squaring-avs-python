# Incredible Squaring AVS Operator

The operator is a core validator component of the Incredible Squaring Actively Validated Service (AVS) built on EigenLayer. It listens for tasks from the blockchain, processes them by computing the square of numbers, and submits signed responses to the aggregator.

## Overview

The Incredible Squaring AVS operator performs the following key functions:

1. **Task Monitoring**: Listens for `NewTaskCreated` events from the task manager contract
2. **Task Processing**: Computes the square of numbers as specified in tasks
3. **Response Signing**: Signs task responses using BLS cryptography
4. **Response Submission**: Sends signed responses to the aggregator via HTTP
5. **Automatic Registration**: Optionally registers with EigenLayer and AVS on startup
6. **Stake Management**: Manages token deposits and allocation strategies

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Blockchain    │────│    Operator      │────│   Aggregator    │
│                 │    │                  │    │                 │
│ - Task Events   │    │ - Listen for     │    │ - Collect sigs  │
│ - Contracts     │    │   tasks          │    │ - Verify sigs   │
│                 │    │ - Compute result │    │ - Aggregate     │
│                 │    │ - Sign response  │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                       ┌──────────────┐
                       │ Key Storage  │
                       │              │
                       │ - BLS Keys   │
                       │ - ECDSA Keys │
                       └──────────────┘
```

## Features

- **Real-time Task Processing**: Automatically processes tasks as they are created
- **BLS Signature Generation**: Cryptographically signs responses using BLS keys
- **Automatic Registration**: Can self-register with EigenLayer and AVS on startup
- **Stake Management**: Handles token deposits and allocation modifications
- **Error Simulation**: Optional failure simulation for testing robustness
- **Comprehensive Logging**: Detailed logging for monitoring and debugging
- **Graceful Error Handling**: Robust error handling for network and processing issues

## Prerequisites

- Python 3.8+
- Access to Ethereum RPC endpoint
- EigenLayer AVS contracts deployed
- BLS and ECDSA private keys for the operator
- Access to aggregator HTTP endpoint
- Contract ABIs for task manager and service manager
- Sufficient ETH for gas fees
- Tokens for staking (if using automatic registration)

## Installation

1. **Install Dependencies**:
```bash
pip install -r requirements.txt
```

2. **Prepare Key Files**:
Generate or obtain BLS and ECDSA key files:
```bash
# BLS key generation (example)
# ECDSA key should be in standard Ethereum keystore format
```

3. **Set up Contract ABIs**:
Ensure the following ABI files are available:
- `abis/IncredibleSquaringServiceManager.json`
- `abis/IncredibleSquaringTaskManager.json`

## Configuration

Create a YAML configuration file (e.g., `config-files/operator.anvil.yaml`):

```yaml
# Ethereum Network Configuration
eth_rpc_url: "http://localhost:8545"
eth_ws_url: "ws://localhost:8545"

# Operator Configuration
operator_address: "0x1234..."
ecdsa_private_key_store_path: "path/to/operator-ecdsa-keystore.json"
bls_private_key_store_path: "path/to/operator-bls-key.json"

# Registration Configuration
register_operator_on_startup: "true"  # Set to "false" to disable auto-registration

# Contract Addresses
service_manager_address: "0xabcd..."
token_strategy_addr: "0xefgh..."
avs_registry_coordinator_address: "0x..."
operator_state_retriever_address: "0x..."
rewards_coordinator_address: "0x..."
permission_controller_address: "0x..."
allocation_manager_address: "0x..."
instant_slasher_address: "0x..."
delegation_manager_address: "0x..."

# Server Configuration
operator_server_ip_port_address: "localhost:8081"
aggregator_server_ip_port_address: "localhost:8080"
prom_metrics_ip_port_address: "localhost:9091"

# Testing Configuration (Optional)
times_failing: 0  # Percentage chance to submit wrong answer for testing
```

## Environment Variables

Set the following environment variables for key passwords:

```bash
export OPERATOR_BLS_KEY_PASSWORD="your_bls_key_password"
export OPERATOR_ECDSA_KEY_PASSWORD="your_ecdsa_key_password"
```

## Usage

### Starting the Operator

```bash
python squaring_operator.py
```

Or with custom configuration:
```bash
# Modify the config path in squaring_operator.py or create a launcher script
python main.py --config config-files/operator.custom.yaml
```

### Operator Lifecycle

1. **Initialization**: Load keys, initialize clients, optionally register
2. **Event Listening**: Monitor blockchain for new task events
3. **Task Processing**: Compute squares of received numbers
4. **Response Signing**: Sign responses with BLS key
5. **Response Submission**: Send to aggregator via HTTP

### Automatic Registration Flow

When `register_operator_on_startup` is enabled, the operator will:

1. **Register with EigenLayer**: Set up as an operator in the delegation system
2. **Deposit Tokens**: Stake 1000 tokens into the specified strategy
3. **Register with AVS**: Join operator set 0 of the Incredible Squaring AVS
4. **Set Allocation Delay**: Configure allocation timing to 0
5. **Modify Allocations**: Set allocation magnitude to 100,000,000

## Task Processing

### Task Event Structure

The operator listens for events with this structure:
```javascript
{
  "taskIndex": 123,
  "task": {
    "numberToBeSquared": 5,
    "taskCreatedBlock": 1000,
    "quorumNumbers": "0x00",
    "quorumThresholdPercentage": 70
  }
}
```

### Processing Logic

1. **Extract Task Data**: Parse task index and number to be squared
2. **Compute Result**: Calculate `number_to_be_squared²`
3. **Optional Failure Simulation**: If configured, occasionally return wrong result
4. **Generate Response**: Create task response object

### Response Signing

The operator signs responses using BLS signatures:

```python
# Encode response data
encoded = eth_abi.encode(["uint32", "uint256"], [task_index, number_squared])
hash_bytes = Web3.keccak(encoded)

# Sign with BLS key
signature = bls_key_pair.sign_message(hash_bytes)
```

### Response Submission

Responses are sent to the aggregator via HTTP POST:

```json
{
  "task_index": 123,
  "number_squared": 25,
  "signature": {"X": "0x...", "Y": "0x..."},
  "block_number": 1000,
  "operator_id": "0x..."
}
```

## Configuration Parameters

### Required Parameters

| Parameter | Description |
|-----------|-------------|
| `operator_address` | Ethereum address of the operator |
| `ecdsa_private_key_store_path` | Path to ECDSA keystore file |
| `bls_private_key_store_path` | Path to BLS key file |
| `eth_rpc_url` | Ethereum RPC endpoint |
| `aggregator_server_ip_port_address` | Aggregator HTTP endpoint |

### Optional Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `register_operator_on_startup` | Auto-register on startup | "false" |
| `times_failing` | Failure simulation percentage | 0 |
| `token_strategy_addr` | Strategy for token staking | Required if auto-registering |
| `operator_server_ip_port_address` | Operator server address | localhost:8081 |

## Key Management

### BLS Key Requirements

- Used for signing task responses
- Must be in the format expected by the EigenSDK
- Password protection recommended

### ECDSA Key Requirements

- Standard Ethereum keystore format (JSON)
- Used for blockchain transactions
- Must have sufficient ETH for gas fees

### Security Best Practices

1. **Secure Key Storage**: Store keys in encrypted formats
2. **Environment Variables**: Use environment variables for passwords
3. **File Permissions**: Restrict access to key files
4. **Backup Keys**: Maintain secure backups of all keys

## Registration Management

### Manual Registration

If auto-registration is disabled, use the CLI tool:

```bash
# Navigate to CLI directory
cd ../cli

# Register with EigenLayer
python main.py register-with-eigenlayer --config ../config-files/operator.anvil.yaml

# Deposit tokens
python main.py deposit --config ../config-files/operator.anvil.yaml

# Register with AVS
python main.py register-with-avs --config ../config-files/operator.anvil.yaml
```

### Registration Parameters

Auto-registration uses these default parameters:
- **Stake Amount**: 1000 tokens (1e21 wei with 18 decimals)
- **Operator Set**: 0 (default quorum)
- **Allocation Delay**: 0 blocks
- **Allocation Magnitude**: 100,000,000

## Monitoring and Logging

### Log Levels

The operator uses Python's logging with INFO level by default:

```python
# Enable debug logging for detailed information
logging.basicConfig(level=logging.DEBUG)
```

### Key Log Messages

- Task processing: Details about received tasks and computed results
- Signature generation: Confirmation of successful response signing
- Response submission: HTTP request results and aggregator responses
- Registration: Auto-registration process status
- Errors: Detailed error information for troubleshooting

### Example Log Output

```
INFO:__main__:Operator initialized successfully
DEBUG:__main__:Listening for new tasks...
DEBUG:__main__:New task created: {...}
DEBUG:__main__:Processing new task numberToBeSquared=5 taskIndex=123
DEBUG:__main__:Signature generated, task id: 123, number squared: 25
DEBUG:__main__:Submitting task response to aggregator
DEBUG:__main__:Successfully sent task response to aggregator
```

## Error Handling

### Common Error Scenarios

1. **Key Loading Failures**: Invalid keystore format or wrong password
2. **Network Issues**: RPC endpoint unavailable or network timeouts
3. **Contract Errors**: Invalid contract addresses or ABI mismatches
4. **Aggregator Communication**: HTTP connection failures or timeouts
5. **Registration Failures**: Insufficient balance or invalid parameters

### Error Recovery

The operator implements robust error handling:

- **Graceful Degradation**: Continues operation despite individual task failures
- **Retry Logic**: Automatic retries for transient network issues
- **Detailed Logging**: Comprehensive error messages for debugging
- **Service Continuity**: Maintains event listening even after errors

## Testing and Debugging

### Failure Simulation

Test aggregator and challenger behavior by enabling failure simulation:

```yaml
times_failing: 10  # 10% chance of wrong answers
```

This causes the operator to occasionally submit incorrect results for testing.

### Debug Mode

Enable detailed logging for troubleshooting:

```python
# In squaring_operator.py
logging.basicConfig(level=logging.DEBUG)
```

### Manual Testing

Test individual components:

```bash
# Test configuration loading
python -c "import yaml; print(yaml.load(open('config-files/operator.anvil.yaml'), yaml.BaseLoader))"

# Test key loading
python -c "from squaring_operator import SquaringOperator; import yaml; op = SquaringOperator(yaml.load(open('config-files/operator.anvil.yaml'), yaml.BaseLoader))"
```

## Performance Considerations

- **Event Polling**: 3-second intervals between blockchain event checks
- **Response Timing**: 3-second delay before sending responses to aggregator
- **Memory Usage**: Minimal memory footprint for key storage and client objects
- **Network Efficiency**: Single HTTP request per task response

## Security Considerations

1. **Private Key Security**: Never expose private keys in logs or config files
2. **Network Security**: Use secure RPC endpoints and HTTPS when possible
3. **Access Control**: Restrict access to operator host and key files
4. **Gas Management**: Monitor ETH balance for transaction fees
5. **Signature Verification**: Ensure BLS signatures are generated correctly

## Troubleshooting

### Common Issues

1. **Key Loading Errors**:
   ```bash
   # Check key file existence and format
   ls -la path/to/keystore.json
   # Verify password environment variable
   echo $OPERATOR_ECDSA_KEY_PASSWORD
   ```

2. **Contract Connection Issues**:
   ```bash
   # Test RPC connectivity
   curl -X POST -H "Content-Type: application/json" \
     --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' \
     http://localhost:8545
   ```

3. **Aggregator Communication Failures**:
   ```bash
   # Test aggregator endpoint
   curl -X POST http://localhost:8080/signature \
     -H "Content-Type: application/json" \
     -d '{"test": "ping"}'
   ```

4. **Registration Issues**:
   ```bash
   # Check operator balance
   # Verify contract addresses
   # Ensure registration order (EigenLayer first, then AVS)
   ```

### Debug Commands

Monitor operator activity:
```bash
# Follow logs in real-time
tail -f operator.log

# Check specific error patterns
grep -i error operator.log
grep -i "task response" operator.log
```

## Integration with AVS Ecosystem

The operator integrates with several components:

- **Task Manager Contract**: Receives task events
- **Service Manager**: Provides contract addresses and configuration
- **Aggregator**: Receives signed task responses
- **EigenLayer Core**: Handles registration and staking
- **AVS Registry**: Manages operator sets and quorums

## Development

### Code Structure

- `SquaringOperator.__init__()`: Initialize operator with configuration
- `start()`: Main event processing loop
- `process_task_event()`: Handle individual task events
- `sign_task_response()`: Generate BLS signatures
- `send_signed_task_response()`: Submit to aggregator
- `register_operator_on_startup()`: Auto-registration flow

### Extending Functionality

To add custom task processing logic:

```python
def process_task_event(self, event):
    # Extract task data
    number_to_be_squared = event["args"]["task"]["numberToBeSquared"]
    
    # Custom processing logic here
    result = self.custom_computation(number_to_be_squared)
    
    # Return standard response format
    return {"referenceTaskIndex": task_index, "numberSquared": result}
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Implement changes with proper error handling
4. Add tests for new functionality
5. Ensure logging is maintained
6. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For questions and support:
- Open an issue on GitHub
- Check the EigenLayer operator documentation
- Review the AVS development guides
- Join the EigenLayer Discord community 