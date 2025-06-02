import yaml
from web3 import Web3

with open("config-files/operator2.anvil.yaml", "r") as f:
    config = yaml.load(f, Loader=yaml.BaseLoader)

private_key = "0xdbda1821b80551c9d65939329250298aa3472ba22feea921c0cf5d620ea67b97"
web3 = Web3(Web3.HTTPProvider(config["eth_rpc_url"]))
account = web3.eth.account.from_key(private_key)
from_address = account.address
nonce = web3.eth.get_transaction_count(from_address)
tx = {
    "nonce": nonce,
    "to": config["operator_address"],
    "value": web3.to_wei(1, "ether"),
    "gas": 21000,
    "gasPrice": web3.to_wei("50", "gwei"),
    "chainId": web3.eth.chain_id,
}
signed_tx = web3.eth.account.sign_transaction(tx, private_key)
tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
