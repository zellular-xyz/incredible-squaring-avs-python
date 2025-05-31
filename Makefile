############################# HELP MESSAGE #############################
.PHONY: $(MAKECMDGOALS)

-----------------------------: ## 

___CONTRACTS___: ## 

build-contracts: ## builds all contracts
	git clone https://github.com/dapphub/ds-test.git contracts/lib/eigenlayer-middleware/lib/ds-test
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


___PYTHON_SETUP___: ## 

setup-and-activate: ## Create venv, activate it, and install dependencies
	python3 -m venv venv && \
	bash -c "source venv/bin/activate && \
	pip install -r requirements.txt && \
	echo 'Virtual environment created, activated, and dependencies installed.' && \
	echo 'For future sessions, activate with: source venv/bin/activate'"

__CLI__: ## 

cli-setup-operator: send-fund cli-register-operator-with-eigenlayer cli-deposit-into-mocktoken-strategy cli-register-operator-with-avs ## registers operator with eigenlayer and avs

cli-register-operator-with-eigenlayer: ## registers operator with delegationManager
	python -m cli.main register-with-eigenlayer

cli-deposit-into-mocktoken-strategy: ## 
	python -m cli.main deposit

cli-register-operator-with-avs: ## 
	python -m cli.main register-with-avs

cli-deregister-operator-with-avs: ## 
	python -m cli.main deregister-from-avs

send-fund: ## sends fund to the operator saved in tests/keys/test.ecdsa.key.json
	cast send 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266 --value 10ether --private-key 0x2a871d0798f97d79848a013d4936a73bf4cc922c825d33c1cf7073dff6d409c6

-----------------------------: ## 
____OFFCHAIN_SOFTWARE___: ## 
start-aggregator: ## 
	python -m aggregator.main

start-operator: ## 
	python -m operator.main

start-challenger: ## 
	python -m challenger.main


__REWARDS__: ##

SENDER_ADDR=0xf39fd6e51aad88f6f4ce6ab8827279cfffb92266

TOKEN_ADDRESS=$(shell jq -r '.addresses.token' contracts/script/deployments/incredible-squaring/31337.json)

create-avs-distributions-root:
	cd contracts && \
		forge script script/SetupDistributions.s.sol --rpc-url http://localhost:8545 \
			--broadcast --sig "runAVSRewards()" -v --sender ${SENDER_ADDR}

create-operator-directed-distributions-root:
	cd contracts && \
		forge script script/SetupDistributions.s.sol --rpc-url http://localhost:8545 \
			--broadcast --sig "runOperatorDirected()" -v --sender ${SENDER_ADDR}

claim-distributions:
	cd contracts && \
		forge script script/SetupDistributions.s.sol --rpc-url http://localhost:8545 \
			--broadcast --sig "executeProcessClaim()" -v --sender ${SENDER_ADDR}

get-deployed-token-address:
	@echo "Deployed token Address: $(TOKEN_ADDRESS)"

claimer-account-token-balance:
	cast balance --erc20 $(TOKEN_ADDRESS) 0x0000000000000000000000000000000000000001
