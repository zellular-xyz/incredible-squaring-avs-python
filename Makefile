############################# HELP MESSAGE #############################
# Make sure the help command stays first, so that it's printed by default when `make` is called without arguments

build-contracts: ## builds all contracts
	cd contracts && forge build

deploy-eigenlayer: ## Deploy eigenlayer
	./tests/anvil/deploy-eigenlayer.sh

deploy-avs: ## Deploy avs
	./tests/anvil/deploy-avs.sh

create-quorum:
	./tests/anvil/create-quorum.sh

modify-allocations:
	./tests/anvil/modify-allocations.sh

uam-permissions:
	./tests/anvil/uam-permissions.sh

set-allocation-delay:
	./tests/anvil/set-allocation-delay.sh

set-allocation-delay-and-modify-allocation: set-allocation-delay modify-allocations

deploy-all: deploy-eigenlayer deploy-avs uam-permissions create-quorum

send-fund: ## sends fund to the operator saved in tests/keys/test.ecdsa.key.json
	cast send 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266 --value 10ether --private-key 0x2a871d0798f97d79848a013d4936a73bf4cc922c825d33c1cf7073dff6d409c6
