import {
  OperatorDeregistered as OperatorDeregisteredEvent,
  OperatorRegistered as OperatorRegisteredEvent,
  OperatorSetParamsUpdated as OperatorSetParamsUpdatedEvent,
  OperatorSocketUpdate as OperatorSocketUpdateEvent,
} from "../generated/RegistryCoordinator/RegistryCoordinator";
import {
  Operator,
  OperatorDeregistered,
  OperatorMap,
  OperatorRegistered,
  OperatorSetParamsUpdated,
  OperatorSocketMap,
  OperatorSocketUpdate,
} from "../generated/schema";

export function handleOperatorDeregistered(
  event: OperatorDeregisteredEvent
): void {
  let entity = new OperatorDeregistered(
    event.transaction.hash.concatI32(event.logIndex.toI32())
  );
  entity.operator = event.params.operator;
  entity.operatorId = event.params.operatorId;

  entity.blockNumber = event.block.number;
  entity.blockTimestamp = event.block.timestamp;
  entity.transactionHash = event.transaction.hash;

  entity.save();

  let opAddress = OperatorMap.load(
    event.params.operatorId.toHexString()
  )!.address;
  let op = Operator.load(opAddress.toHexString())!;
  op.blockNumber = event.block.number;
  op.blockTimestamp = event.block.timestamp;
  op.transactionHash = event.transaction.hash;
  op.logIndex = event.logIndex;
  op.registered = false;
  op.save();
}

export function handleOperatorRegistered(event: OperatorRegisteredEvent): void {
  let entity = new OperatorRegistered(
    event.transaction.hash.concatI32(event.logIndex.toI32())
  );
  entity.operator = event.params.operator;
  entity.operatorId = event.params.operatorId;

  entity.blockNumber = event.block.number;
  entity.blockTimestamp = event.block.timestamp;
  entity.transactionHash = event.transaction.hash;

  entity.save();

  let socket = OperatorSocketMap.load(
    event.params.operatorId.toHexString()
  )!.socket;

  let op = Operator.load(event.params.operator.toHexString())!;
  op.operatorId = event.params.operatorId;
  op.blockNumber = event.block.number;
  op.blockTimestamp = event.block.timestamp;
  op.createBlockNumber = event.block.number;
  op.createBlockTimestamp = event.block.timestamp;
  op.transactionHash = event.transaction.hash;
  op.logIndex = event.logIndex;
  op.registered = true;
  op.socket = socket;
  op.save();

  let opMap = new OperatorMap(event.params.operatorId.toHexString());
  opMap.address = event.params.operator;
  opMap.save();
}

export function handleOperatorSetParamsUpdated(
  event: OperatorSetParamsUpdatedEvent
): void {
  let entity = new OperatorSetParamsUpdated(
    event.transaction.hash.concatI32(event.logIndex.toI32())
  );
  entity.quorumNumber = event.params.quorumNumber;
  entity.operatorSetParams_maxOperatorCount =
    event.params.operatorSetParams.maxOperatorCount;
  entity.operatorSetParams_kickBIPsOfOperatorStake =
    event.params.operatorSetParams.kickBIPsOfOperatorStake;
  entity.operatorSetParams_kickBIPsOfTotalStake =
    event.params.operatorSetParams.kickBIPsOfTotalStake;

  entity.blockNumber = event.block.number;
  entity.blockTimestamp = event.block.timestamp;
  entity.transactionHash = event.transaction.hash;

  entity.save();
}

export function handleOperatorSocketUpdate(
  event: OperatorSocketUpdateEvent
): void {
  let entity = new OperatorSocketUpdate(
    event.transaction.hash.concatI32(event.logIndex.toI32())
  );
  entity.operatorId = event.params.operatorId;
  entity.socket = event.params.socket;

  entity.blockNumber = event.block.number;
  entity.blockTimestamp = event.block.timestamp;
  entity.transactionHash = event.transaction.hash;

  entity.save();

  let map = new OperatorSocketMap(event.params.operatorId.toHexString());
  map.socket = event.params.socket;
  map.save();

  let op = OperatorMap.load(event.params.operatorId.toHexString());
  if(op !== null) {
    let opData = Operator.load(op.address.toHexString())!;
    opData.blockNumber = event.block.number;
    opData.blockTimestamp = event.block.timestamp;
    opData.transactionHash = event.transaction.hash;
    opData.logIndex = event.logIndex;
    opData.socket = event.params.socket;
    opData.save();
  }
}
