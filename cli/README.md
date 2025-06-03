# Incredible Squaring AVS CLI

A command-line interface (CLI) tool for managing operator operations in the Incredible Squaring Actively Validated Service (AVS). This tool provides essential commands for operator registration, deregistration, and token staking operations.

## Overview

The Incredible Squaring AVS CLI simplifies operator management by providing easy-to-use commands for:

1. **EigenLayer Registration**: Register operators with the EigenLayer protocol
2. **AVS Registration**: Register operators with the Incredible Squaring AVS
3. **AVS Deregistration**: Deregister operators from the AVS
4. **Token Deposits**: Deposit tokens into staking strategies
5. **Operator Status**: Check operator registration and stake status

## Features

- **Simple Command Interface**: Intuitive command-line interface for all operator operations
- **Configuration Management**: YAML-based configuration for easy environment management
- **Logging Support**: Configurable logging levels for debugging and monitoring
- **Transaction Handling**: Automatic transaction submission and receipt verification
- **Status Reporting**: Real-time operator status and registration information

## Prerequisites

- Python 3.8+
- Access to Ethereum RPC endpoint
- EigenLayer contracts deployed
- Operator ECDSA private key
- Token strategy contracts deployed
- Sufficient ETH for gas fees
- Tokens for staking (if using deposit command)

## Installation

1. **Install Dependencies**:
```bash
pip install -r requirements.txt
```

2. **Ensure SquaringOperator Module**:
Make sure the `squaring_operator` module is available in your Python path or installed.

## Configuration

Create a YAML configuration file (default: `config-files/operator.anvil.yaml`):

```yaml
# Ethereum Network Configuration
eth_rpc_url: "http://localhost:8545"
eth_ws_url: "ws://localhost:8545"

# Operator Configuration
operator_address: "0x1234..."
ecdsa_private_key_store_path: "path/to/operator-keystore.json"

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
prom_metrics_ip_port_address: "localhost:9091"
```

## Usage

### Basic Command Structure

```bash
python main.py [--log-level LEVEL] [--config CONFIG_PATH] <command>
```

### Available Commands

#### 1. Register with EigenLayer

Register the operator with the EigenLayer protocol:

```bash
python main.py register-with-eigenlayer --config config-files/operator.anvil.yaml
```

This command:
- Registers the operator with EigenLayer's delegation manager
- Sets up the operator for receiving delegations
- Must be completed before AVS registration

#### 2. Register with AVS

Register the operator with the Incredible Squaring AVS:

```bash
python main.py register-with-avs --config config-files/operator.anvil.yaml
```

This command:
- Sets the operator as its own appointee
- Creates a total delegated stake quorum with specified parameters
- Registers the operator for operator set 0
- Displays the operator's registration status

**Quorum Parameters**:
- Operator Set Params: `(10, 10000, 2000)`
- Minimum Stake Required: `1,000,000` (base units)
- Strategy Weight: `10000`

#### 3. Deregister from AVS

Remove the operator from the Incredible Squaring AVS:

```bash
python main.py deregister-from-avs --config config-files/operator.anvil.yaml
```

This command:
- Deregisters the operator from operator set 0
- Removes the operator from active validation duties
- Operator can be re-registered later if needed

#### 4. Deposit into Strategy

Deposit tokens into a staking strategy:

```bash
python main.py deposit --config config-files/operator.anvil.yaml
```

This command:
- Deposits `1 ETH` (1000000000000000000 wei) into the specified strategy
- Increases the operator's staking power
- Required for meeting minimum stake requirements

### Command Options

#### Global Options

| Option | Description | Default |
|--------|-------------|---------|
| `--log-level` | Set logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) | INFO |
| `--config` | Path to configuration file | `config-files/operator.anvil.yaml` |

#### Example with Custom Configuration

```bash
python main.py --log-level DEBUG --config /path/to/custom-config.yaml register-with-avs
```

## Typical Operator Setup Flow

For a new operator, follow this sequence:

1. **Prepare Configuration**:
   ```bash
   # Edit your configuration file with correct addresses and keys
   nano config-files/operator.anvil.yaml
   ```

2. **Deposit Tokens** (if needed):
   ```bash
   python main.py deposit --config config-files/operator.anvil.yaml
   ```

3. **Register with EigenLayer**:
   ```bash
   python main.py register-with-eigenlayer --config config-files/operator.anvil.yaml
   ```

4. **Register with AVS**:
   ```bash
   python main.py register-with-avs --config config-files/operator.anvil.yaml
   ```

5. **Verify Registration**:
   The registration command will automatically display operator status.

## Configuration Parameters

### Required Parameters

| Parameter | Description |
|-----------|-------------|
| `operator_address` | Ethereum address of the operator |
| `ecdsa_private_key_store_path` | Path to encrypted keystore file |
| `service_manager_address` | AVS service manager contract address |
| `token_strategy_addr` | Strategy contract address for token staking |
| `eth_rpc_url` | Ethereum RPC endpoint |

### Optional Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `eth_ws_url` | Ethereum WebSocket endpoint | Derived from RPC URL |
| `operator_server_ip_port_address` | Operator server address | localhost:8081 |
| `prom_metrics_ip_port_address` | Prometheus metrics address | localhost:9091 |

## Environment Variables

Set the following environment variable for keystore password:

```bash
export OPERATOR_ECDSA_KEY_PASSWORD="your_keystore_password"
```

## Logging

The CLI supports multiple logging levels:

- **DEBUG**: Detailed execution information
- **INFO**: General operational messages (default)
- **WARNING**: Warning messages
- **ERROR**: Error messages only
- **CRITICAL**: Critical errors only

Example with debug logging:
```bash
python main.py --log-level DEBUG register-with-avs
```

## Transaction Management

The CLI automatically handles:

- **Gas Estimation**: Automatic gas limit calculation
- **Nonce Management**: Proper transaction sequencing
- **Receipt Verification**: Confirms transaction success
- **Error Handling**: Provides clear error messages for failed transactions

## Troubleshooting

### Common Issues

1. **Transaction Failures**:
   ```bash
   # Check operator balance
   # Verify contract addresses in config
   # Ensure sufficient gas
   ```

2. **Configuration Errors**:
   ```bash
   # Verify YAML syntax
   # Check file paths exist
   # Validate contract addresses
   ```

3. **Key Loading Issues**:
   ```bash
   # Verify keystore file format
   # Check ECDSA password environment variable
   # Ensure file permissions are correct
   ```

4. **Registration Failures**:
   ```bash
   # Ensure EigenLayer registration is completed first
   # Check minimum stake requirements
   # Verify operator is not already registered
   ```

### Debug Commands

Check operator status:
```bash
python main.py --log-level DEBUG register-with-avs --config your-config.yaml
```

Validate configuration:
```bash
# Test with a simple operation first
python main.py --log-level DEBUG deposit --config your-config.yaml
```

## Error Codes

The CLI returns the following exit codes:

- `0`: Success
- `1`: Failure (transaction failed, configuration error, etc.)

## Security Considerations

1. **Private Key Security**: Store ECDSA keys in encrypted keystores
2. **Configuration Security**: Protect configuration files with sensitive data
3. **Network Security**: Use secure RPC endpoints
4. **Environment Variables**: Set keystore passwords via environment variables

## Advanced Usage

### Custom Configuration Files

Create environment-specific configuration files:

```bash
# Development
python main.py --config config-files/operator.dev.yaml register-with-avs

# Testnet
python main.py --config config-files/operator.testnet.yaml register-with-avs

# Mainnet
python main.py --config config-files/operator.mainnet.yaml register-with-avs
```

### Batch Operations

Automate multiple operations:

```bash
#!/bin/bash
CONFIG="config-files/operator.anvil.yaml"

echo "Depositing tokens..."
python main.py deposit --config $CONFIG

echo "Registering with EigenLayer..."
python main.py register-with-eigenlayer --config $CONFIG

echo "Registering with AVS..."
python main.py register-with-avs --config $CONFIG

echo "Operator setup complete!"
```

## Integration with Operator Service

After successful registration, start the operator service:

```bash
# Navigate to operator directory
cd ../operator

# Start the operator service
python main.py --config ../config-files/operator.anvil.yaml
```

## Development

### Code Structure

- `main.py`: CLI entry point and argument parsing
- `register_with_eigenlayer()`: EigenLayer registration logic
- `register_with_avs()`: AVS registration and quorum setup
- `deregister_from_avs()`: AVS deregistration logic
- `deposit_into_strategy()`: Token staking functionality

### Adding New Commands

To add a new command:

1. Create a handler function
2. Add it to the `commands` dictionary
3. Add argument parser configuration
4. Implement the command logic

```python
def new_command(config_path):
    # Implementation
    return True

# Add to commands dictionary
commands = {
    # ... existing commands
    "new-command": new_command,
}
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Implement changes with proper error handling
4. Add tests for new functionality
5. Update documentation
6. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For questions and support:
- Open an issue on GitHub
- Check the EigenLayer operator documentation
- Review the AVS development guides
- Join the EigenLayer Discord community 