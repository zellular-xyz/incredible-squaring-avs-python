import { OperatorStakeUpdate as OperatorStakeUpdateEvent } from "../generated/StakeRegistry/StakeRegistry";
import { Operator, OperatorMap, OperatorStakeUpdate } from "../generated/schema";

export function handleOperatorStakeUpdate(
  event: OperatorStakeUpdateEvent
): void {
  let entity = new OperatorStakeUpdate(
    event.transaction.hash.concatI32(event.logIndex.toI32())
  );
  entity.operatorId = event.params.operatorId;
  entity.quorumNumber = event.params.quorumNumber;
  entity.stake = event.params.stake;

  entity.blockNumber = event.block.number;
  entity.blockTimestamp = event.block.timestamp;
  entity.transactionHash = event.transaction.hash;

  entity.save();

  if (event.params.quorumNumber == 0) {
    let opAddress = OperatorMap.load(event.params.operatorId.toHexString())!.address;
    let op = Operator.load(opAddress.toHexString())!;
    op.blockNumber = event.block.number;
    op.blockTimestamp = event.block.timestamp;
    op.transactionHash = event.transaction.hash;
    op.logIndex = event.logIndex;
    op.stake = event.params.stake;
    op.save();
  }
}
