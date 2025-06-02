from eigensdk.crypto.bls.attestation import G1Point, G2Point

from avs.aggregator import Aggregator


class MockAggregator(Aggregator):
    def __init__(self, config):
        super().__init__(config)
        self.operators = {
            "0xc4c210300e28ab4ba70b7fbb0efa557d2a2a5f1fbfa6f856e4cf3e9d766a21dc": {
                "id": "0xf39fd6e51aad88f6f4ce6ab8827279cfffb92266",
                "operatorId": "0xc4c210300e28ab4ba70b7fbb0efa557d2a2a5f1fbfa6f856e4cf3e9d766a21dc",
                "socket": "operator-socket",
                "stake": 1000.0,
                "public_key_g1": G1Point(
                    "643552363890320897587044283125191574906281609959531590546948318138132520777",
                    "7028377728703212953187883551402495866059211864756496641401904395458852281995",
                ),
                "public_key_g2": G2Point(
                    "10049360286681290772545787829932277430329130488480401390150843123809685996135",
                    "15669747281918965782125375489377843702338327900115142954223823046525120542933",
                    "4979648979879607838890666154119282514313691814432950078096789133613246212107",
                    "14982008408420160629923179444218881558075572058100484023255790835506797851583",
                ),
            }
        }

    def operators_info(self, block):
        return self.operators
