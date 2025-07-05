import { NewPubkeyRegistration as NewPubkeyRegistrationEvent } from "../generated/BLSApkRegistry/BLSApkRegistry";
import {
  NewPubkeyRegistration,
  Operator
} from "../generated/schema";

export function handleNewPubkeyRegistration(
  event: NewPubkeyRegistrationEvent
): void {
  let entity = new NewPubkeyRegistration(
    event.transaction.hash.concatI32(event.logIndex.toI32())
  );
  entity.operator = event.params.operator;
  entity.pubkeyG1_X = event.params.pubkeyG1.X;
  entity.pubkeyG1_Y = event.params.pubkeyG1.Y;
  entity.pubkeyG2_X = event.params.pubkeyG2.X;
  entity.pubkeyG2_Y = event.params.pubkeyG2.Y;

  entity.blockNumber = event.block.number;
  entity.blockTimestamp = event.block.timestamp;
  entity.transactionHash = event.transaction.hash;

  entity.save();

  let op = new Operator(event.params.operator.toHexString());
  op.registered = false;
  op.pubkeyG1_X = event.params.pubkeyG1.X;
  op.pubkeyG1_Y = event.params.pubkeyG1.Y;
  op.pubkeyG2_X = event.params.pubkeyG2.X;
  op.pubkeyG2_Y = event.params.pubkeyG2.Y;
  op.blockNumber = event.block.number;
  op.blockTimestamp = event.block.timestamp;
  op.transactionHash = event.transaction.hash;
  op.logIndex = event.logIndex;
  op.save();
}
