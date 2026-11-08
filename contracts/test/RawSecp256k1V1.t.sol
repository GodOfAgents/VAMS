// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
import {Test} from "forge-std/Test.sol";
import {Vm} from "forge-std/Vm.sol";
import {RawSecp256k1V1 as Raw} from "../src/trust/RawSecp256k1V1.sol";

/// @dev Synthetic arithmetic harness only; no issuer, registry, consent or effect authority.
contract RawSecp256k1V1Harness {
    function verifyMemory(bytes32 digest,bytes memory key,bytes memory signature) external view returns(bool) {
        return Raw.verifyDigest(digest,key,signature);
    }
    function verifyCalldata(bytes32 digest,bytes calldata key,bytes calldata signature) external view returns(bool) {
        return Raw.verifyDigestCalldata(digest,key,signature);
    }
}
contract RawSecp256k1V1Tests is Test {
    uint256 constant N=0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141;
    RawSecp256k1V1Harness private harness;
    function setUp() public { harness=new RawSecp256k1V1Harness(); }
    function _check(bytes32 digest,bytes memory key,bytes memory signature,bool expected) private {
        assertEq(harness.verifyMemory(digest,key,signature),expected,"memory differs from existing Python wire verifier");
        assertEq(harness.verifyCalldata(digest,key,signature),expected,"calldata differs from existing Python wire verifier");
    }
    function testVector_ordinary_sha256_message() public {
        _check(0x69a038e4ca6e8c67f96151d87f8e91bcd027bf0a69a7520bf1e5584745207155,hex"79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8",hex"eac78a87b20394063211978821427b2cbb2d1bc343306e6d0e88e70b53b7cc3e0d4aef8429aa89fec05bf3b2b27f0ac3dd9b19f9aae46d1b9d15d335213a3fda",true);
    }
    function testVector_maximum_digest() public {
        _check(0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff,hex"c6047f9441ed7d6d3045406e95c07cd85c778e4b8cef3ca7abac09b95c709ee51ae168fea63dc339a3c58419466ceaeef7f632653266d0e1236431a950cfe52a",hex"5f17305d4134e077cdd6a354d928949bd4d63647eeee127622c25006b19fad7901b551ea85ae2f335e5253e688370d49981fe202af925dce26a1dbd25b439a08",true);
    }
    function testVector_zero_digest_known_fixture_key() public {
        _check(0x0000000000000000000000000000000000000000000000000000000000000000,hex"f9308a019258c31049344f85f89d5229b531c845836f99b08601f113bce036f9388f7b0f632de8140fe337e62a37f3566500a99934c2231b6cb9fd7584b8e672",hex"8a35e0d0fe283c904bd8669503a39b66e7823dac2001df73e3cfd2cb5634e9481bb1cfb45f4628da22b1a54744bd6c56ee23da6469d62d946181bc87faa58221",true);
    }
    function testVector_opposite_generator_public_key() public {
        _check(0xcb5202803204c13797e725ae4415d9170f7afc530ade4fd442c44fd307922180,hex"79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798b7c52588d95c3b9aa25b0403f1eef75702e84bb7597aabe663b82f6f04ef2777",hex"7d4ac1e79de6b9b4931ce672fc7e369672a2741ce8e576ca6cbdd5bd391770912263c12cfaa83920418208d0a6dc1c42d18ddb582863d2d6f58f6f3559f7b13f",true);
    }
    function testVector_joint_R_and_Q_x_overflow() public {
        _check(0x0000000000000000000000000000000000000000000000000000000000000000,hex"fffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd036414336b1aa62eb77c1973025cbcbea9740eed8eacdab8772268b395064453269d1d3",hex"00000000000000000000000000000000000000000000000000000000000000020000000000000000000000000000000000000000000000000000000000000002",true);
    }
    function testVector_R_x_overflow_with_normal_Q() public {
        _check(0x0000000000000000000000000000000000000000000000000000000000000002,hex"fa080d6569edae14025c385d49d06a25b116121767026fe837249ff0a5bcbac771aeed5573db3682d4f047d920f14c61b39cfd546ef2de3f4a8cf17c2e7a964d",hex"00000000000000000000000000000000000000000000000000000000000000020000000000000000000000000000000000000000000000000000000000000002",true);
    }
    function testVector_Q_x_overflow_with_normal_R() public {
        _check(0xdd4563fbecd6d7b83e1ea18b4a6ba1e221a675f2fae9c6dfba0c8e4ebb937abc,hex"fffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd036414336b1aa62eb77c1973025cbcbea9740eed8eacdab8772268b395064453269d1d3",hex"dd4563fbecd6d7b83e1ea18b4a6ba1e221a675f2fae9c6dfba0c8e4ebb937abc22ba9c0413292847c1e15e74b5945e1c990866f3b45ed95c05c5d03e14a2c685",true);
    }
    function testVector_valid_low_S_exact_half_order() public {
        _check(0x0000000000000000000000000000000000000000000000000000000000000001,hex"94261278d4136e358ad969239809940f6b35332881366ac92fbc20c367067c5002bc311960e21b72e4df82b4283386d10064e041735ba6224ded29d2d8fc1d73",hex"79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f817987fffffffffffffffffffffffffffffff5d576e7357a4501ddfe92f46681b20a0",true);
    }
    function testVector_backend_signature_01() public {
        _check(0x0358f1a3292394902f536f7b70491c6fa16afce793c1375825d2458ae9e93136,hex"79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8",hex"d20800ea18be38697d2615f6d922f8a7dbd0b01abf031eff73f17c46fd8ef1946ba63ccb7b0f72c57912ce2caf3bb38fe76644cfbfb8af9fedb2d7f7f3a86fd0",true);
    }
    function testVector_backend_signature_02() public {
        _check(0xf430052eccf9bac23ffea5798cbbd833b3b87f679211d8151db361a49ea0608b,hex"c6047f9441ed7d6d3045406e95c07cd85c778e4b8cef3ca7abac09b95c709ee51ae168fea63dc339a3c58419466ceaeef7f632653266d0e1236431a950cfe52a",hex"3e165c590b12f8977bf203dcf4df8995c28a7f8026bbd0e195ca903d8276c6d40219a95f3eadc9caf972a88ae55b10b33d780c9b2c8a02b067f28de593410c24",true);
    }
    function testVector_backend_signature_03() public {
        _check(0xee04629379b4aea41ed7686eaf1b8dc7578b930e7a5d71ef4eee545cf85b0c86,hex"f9308a019258c31049344f85f89d5229b531c845836f99b08601f113bce036f9388f7b0f632de8140fe337e62a37f3566500a99934c2231b6cb9fd7584b8e672",hex"70b8e11bc73ae3b9c63e8d631a8b7da25cb2996393e364b589e6a30fe9d1682f43034c69c585280c0a65c757890b432daa0f83bc886453b0e94a532dd7008aaa",true);
    }
    function testVector_backend_signature_04() public {
        _check(0x85592b259885bea89c90b58322eeb9ddd74517c19b61236e4cc97e84be203b53,hex"e493dbf1c10d80f3581e4904930b1404cc6c13900ee0758474fa94abe8c4cd1351ed993ea0d455b75642e2098ea51448d967ae33bfbdfe40cfe97bdc47739922",hex"75602727cd5f896550aa27bbeaf48295b1fb665af078deffb31fe7467c9d64a00ab3f075a1bbbd15abaa4468ab37fa6188957082375590e3563223d7642f680a",true);
    }
    function testVector_backend_signature_05() public {
        _check(0xed2cc2d9f62b5f40ef5d30980e7b352315b66bcad81cd652ea2872db011916a7,hex"2f8bde4d1a07209355b4a7250a5c5128e88b84bddc619ab7cba8d569b240efe4d8ac222636e5e3d6d4dba9dda6c9c426f788271bab0d6840dca87d3aa6ac62d6",hex"83f0caa6f6b7ebf1133bdcd02aed6a3ca9a1585ad2cdb90c143e31cf6782cacd11b2d819e2b86840061a09c2588669007318bae230014bd2f432b0c578ac90df",true);
    }
    function testVector_backend_signature_06() public {
        _check(0x3912a26c3107186315ee35d7578cae7d4c166244e9f668480e026e405427dc80,hex"fff97bd5755eeea420453a14355235d382f6472f8568a18b2f057a1460297556ae12777aacfbb620f3be96017f45c560de80f0f6518fe4a03c870c36b075f297",hex"bbd3d7a0165edc7c19833bc2408e7196ebc4c4bdac73f4768cff28a9ffcf3dba763f9c9932f793d3397fe02e804fb80aaf671533002c976c00a9e6651337d8d3",true);
    }
    function testVector_backend_signature_07() public {
        _check(0x2fb8c3a6475b4f663c99d8806b7ca5cbaef66d59f8a7617399f71b3fbbd58b1a,hex"5cbdf0646e5db4eaa398f365f2ea7a0e3d419b7e0330e39ce92bddedcac4f9bc6aebca40ba255960a3178d6d861a54dba813d0b813fde7b5a5082628087264da",hex"abd66b4a82ac37412d2794ee49662ba02f7f0638881848e1972368371d91ad36625ab5b69dba5b2e1c634cfdf92ba4f73dcbe3d45b1f91f155926df306bd2358",true);
    }
    function testVector_backend_signature_08() public {
        _check(0xd926c7fb960202954b3a42925bb3e3e865c8ec89d2b7d81776ceaab56a4c7769,hex"2f01e5e15cca351daff3843fb70f3c2f0a1bdd05e5af888a67784ef3e10a2a015c4da8a741539949293d082a132d13b4c2e213d6ba5b7617b5da2cb76cbde904",hex"2f5c7b60070243aa262fb7f35377428d85b3f1dd7f32daad3339488d9637593240141648155e2f6b9433bcf93dc38ed69b38b56f5d3a67bd5407aadbbf8c1946",true);
    }
    function testVector_backend_signature_09() public {
        _check(0x4c07794f3365d774412eeeef6c01fd8122ab621937912539d9088157ea705527,hex"acd484e2f0c7f65309ad178a9f559abde09796974c57e714c35f110dfc27ccbecc338921b0a7d9fd64380971763b61e9add888a4375f8e0f05cc262ac64f9c37",hex"502e55095b2c6f24c23f9808eb6c577a83be36c0c4649b875a20e6c939312f5e786d7d84590e1fe32d42b4db9bb0020d20f1a7c5e4f44663f41a555f12a4023a",true);
    }
    function testVector_backend_signature_10() public {
        _check(0xc153e8cbc025f3e691b924320be1ff6d363ce22d4de9b87791c9a3c59453b81f,hex"a0434d9e47f3c86235477c7b1ae6ae5d3442d49b1943c2b752a68e2a47e247c7893aba425419bc27a3b6c7e693a24c696f794c2ed877a1593cbee53b037368d7",hex"0fe2f44cae993a3526ebfc7e669e9f79f763bdd3235e8656af92b6641dda88db2ceee9e5e2e3530ecde3852b75138690012b4f6fe68b73484586eb17c0b0fec0",true);
    }
    function testVector_backend_signature_11() public {
        _check(0xcc8ad48361a033bf1e464c173e8a38bf148d0719ef252897b1607cda7af6661a,hex"774ae7f858a9411e5ef4246b70c65aac5649980be5c17891bbec17895da008cbd984a032eb6b5e190243dd56d7b7b365372db1e2dff9d6a8301d74c9c953c61b",hex"f8cd5ddc4ed6998c18e4c5e3ddea06b955de7399bf743c040baaa20d481f6dad3544560b611bdf58123c79e6bdb79c0ddc69f182791e93941880ea2b59dd6cd7",true);
    }
    function testVector_backend_signature_12() public {
        _check(0x121f2e6bfe7d0b4befa965ea0383428aefd30215c508de892f1fe1ff627f0468,hex"d01115d548e7561b15c38f004d734633687cf4419620095bc5b0f47070afe85aa9f34ffdc815e0d7a8b64537e17bd81579238c5dd9a86d526b051b13f4062327",hex"ebb8e5b40bc21417f1ad820eece15c8cba2e4b2183a54ea81404a8fa4a00987b513880e3d58e95d7c64d363da7c1a12758163519fc89e975da276a6bec51a8b2",true);
    }
    function testVector_backend_signature_13() public {
        _check(0x87f92a34822b2ae80b7606ad8e84514fb05d390be628c7a10b9ed7f5b8590b43,hex"f28773c2d975288bc7d1d205c3748651b075fbc6610e58cddeeddf8f19405aa80ab0902e8d880a89758212eb65cdaf473a1a06da521fa91f29b5cb52db03ed81",hex"07096002618722dd5289d1c99183b52cd8a18ba230d0bc4b3de059b36ccf9cb748f38079de2a092e0af2d56b74c569a1023b617f023864b49f21d3cdde35b772",true);
    }
    function testVector_backend_signature_14() public {
        _check(0xc3756b196b3e21025230fc65a43a227af5b22e3370af4287c9e0ee31a9b1a422,hex"499fdf9e895e719cfd64e67f07d38e3226aa7b63678949e6e49b241a60e823e4cac2f6c4b54e855190f044e4a7b3d464464279c27a3f95bcc65f40d403a13f5b",hex"79044466edec10e635ade8f8171f9badefe50fa32d34110bde611010296a8cf14baf4c630b978605284a7f997ef2454306097c819224626a3f1772286842bf76",true);
    }
    function testVector_backend_signature_15() public {
        _check(0x5b2a90319fe049342f1b844735478e534d067e508267bc79bb83c123835ef5ae,hex"d7924d4f7d43ea965a465ae3095ff41131e5946f3c85f79e44adbcf8e27e080e581e2872a86c72a683842ec228cc6defea40af2bd896d3a5c504dc9ff6a26b58",hex"48c28e411d6a4988cc0d03e908dec621df81bcf7fe107639561eb57cf7f08237786f8de38a4bc7cca77b63fc72adeb5a05724b1a1550bea2a1dfc7571774ec44",true);
    }
    function testVector_backend_signature_16() public {
        _check(0x57e9a5dc1ada1cf53c78030dd769cb16f11f77bb7f1fe8140818697c9f0779d1,hex"e60fce93b59e9ec53011aabc21c23e97b2a31369b87a5ae9c44ee89e2a6dec0af7e3507399e595929db99f34f57937101296891e44d23f0be1f32cce69616821",hex"6eb761a2845ebe41113565ffcddacdda1908a13ebf3c4ba9394c86d2dbe281144e0568f2dec8b14c3577e7ed43da1d829a334b46f75e6bceb12bbb3d6f03e351",true);
    }
    function testVector_backend_signature_17() public {
        _check(0x0befd8686322571a531e4485737bac88481b147e985ddee043af3af138e14118,hex"defdea4cdb677750a420fee807eacf21eb9898ae79b9768766e4faa04a2d4a344211ab0694635168e997b0ead2a93daeced1f4a04a95c0f6cfb199f69e56eb77",hex"94e1fb7e511ba9c994fc56f348f7cd903d143e43e2599fe347bc34cf0c510b0a11731ae1758dd6df4a0f01ae1a9006d772bf07f6dc7f9eeb948ef67413b57b58",true);
    }
    function testVector_backend_signature_18() public {
        _check(0x0fd13f1844ba1146c9ba2eaf7ac890aacca70988e28855f87309b3b3544e8025,hex"5601570cb47f238d2b0286db4a990fa0f3ba28d1a319f5e7cf55c2a2444da7ccc136c1dc0cbeb930e9e298043589351d81d8e0bc736ae2a1f5192e5e8b061d58",hex"2668bfd38975f9deb6642b9fe5ed5d8316e9d1fcef9faf1012c3428f91610d5b1a891dc6a71b754c4b2f3efaef146d51c1c96a67583fde3c9ef0d4365991edf7",true);
    }
    function testVector_backend_signature_19() public {
        _check(0x69ef292cd7da3ec28ecbb7d2d43a3eeff1c500fd3ced3033b38bd14d3f302f6b,hex"2b4ea0a797a443d293ef5cff444f4979f06acfebd7e86d277475656138385b6c85e89bc037945d93b343083b5a1c86131a01f60c50269763b570c854e5c09b7a",hex"5ea82ca4268974bc34797b54fc3f7b5bab405de1d212c447d56f2ecd8b812b4f5107f74abf7963a0added6d542c80c9d063717dcbc4fe01eeeb625e4f80124f8",true);
    }
    function testVector_backend_signature_20() public {
        _check(0x2eaa7fb2ae1073e450b1868604dd513016dc8e448654c9b99bb42046612fad90,hex"4ce119c96e2fa357200b559b2f7dd5a5f02d5290aff74b03f3e471b273211c9712ba26dcb10ec1625da61fa10a844c676162948271d96967450288ee9233dc3a",hex"5fe4bc0cc7fc0a304036cf6c01141ada8b3b36f363ca1c74c7dc29fca4cf0dbb4960b3912a6f2159b16de2c25ccb4ec9f28fd8f86373a59f4274ceb49df5a4fd",true);
    }
    function testVector_backend_signature_21() public {
        _check(0x828d7d8f03f03810f95fc1b49448c50e87b2857f2a4966439acf8ac4f8fa8c1d,hex"352bbf4a4cdd12564f93fa332ce333301d9ad40271f8107181340aef25be59d5321eb4075348f534d59c18259dda3e1f4a1b3b2e71b1039c67bd3d8bcf81998c",hex"7035a0328a025e34b22557829fbf36ccfc3ad1f0424cd4d93dbc3cb7b64572941e7a19324170921d673406294f2bd951c2ce1bb5c5c8028cda4780d7e0e81637",true);
    }
    function testVector_backend_signature_22() public {
        _check(0xb81a7dbf0f12ad8f78192ddd1d21e3bad52d929b6360c0061433f9a7f27a7641,hex"421f5fc9a21065445c96fdb91c0c1e2f2431741c72713b4b99ddcb316f31e9fc2b90f16d11dabdb616f6db7e225d1e14743034b37b223115db20717ad1cd6781",hex"abbd58b446552dd4186cee10d2d5daa02b0a565b8745730b6c735117182177df5464fb78a388af5148729fa435724e311fc896dc4ba8b0b554670a47837f407e",true);
    }
    function testVector_backend_signature_23() public {
        _check(0xf5fd76d9cb6da7999a01965df0151d01c6e98e4166ecb3af84b47a27fc210285,hex"2fa2104d6b38d11b0230010559879124e42ab8dfeff5ff29dc9cdadd4ecacc3f02de1068295dd865b64569335bd5dd80181d70ecfc882648423ba76b532b7d67",hex"870533002603b70ff8fee43f483c2376d981c2f1f9427b4f7929494a481e8b83019ab9d7805013e504e0f786278b64b76106836c7a6e0f1e3f1cc4ad13b34efe",true);
    }
    function testVector_backend_signature_24() public {
        _check(0xc72263423bb7fe7e990971f1e192ce2164d8cba1e75de7d020b6310d8e309e74,hex"fe72c435413d33d48ac09c9161ba8b09683215439d62b7940502bda8b202e6ce6851de067ff24a68d3ab47e09d72998101dc88e36b4a9d22978ed2fbcf58c5bf",hex"7fa67fa6a9757e9f6157456401a13a6facfd06c9ecd7a434d8211590f03c7209034ad1c590e5cd6c4efb89d0fcfd96156d6bda0f5f589fe6237f8f0fcd8ce776",true);
    }
    function testVector_backend_signature_25() public {
        _check(0x5c60b958b140c7c5cb037dfae66bfd92e74b823f0c8d15c2a427da149668dd5e,hex"9248279b09b4d68dab21a9b066edda83263c3d84e09572e269ca0cd7f545371473016f7bf234aade5d1aa71bdea2b1ff3fc0de2a887912ffe54a32ce97cb3402",hex"9ef65c1f4cb495b6601272930e6b2371502027c65d89535e418c6e4a157d364c462c5c1540cc9fbe830b4ce634f0c07a351181f2f7c02a39773921aeb8234b8c",true);
    }
    function testVector_backend_signature_26() public {
        _check(0xe984090fba962f3881b59bbed3fa6b0796b3b1183aa6e239f885247344ed0a49,hex"6687cdb5b650d558f40cbdefc8e40997c03fe1b2abb840885e5cad81710c4c8a3fd502b3111178b11a1fa873825c72000ef8e529f033f272b32e83b25c83ad64",hex"fe8e17f6398fb9f129e475f62a5e1e600dfd16afc3edbc2ca9c302d9d190129337471675654792f59f57f10c0d4099d25bfcc00fc3f66fd16bac737f0892f8e8",true);
    }
    function testVector_backend_signature_27() public {
        _check(0xeab3b74eb6ed09df27e5b0db46c450942ce240928e22677ba20d6458b581ba85,hex"daed4f2be3a8bf278e70132fb0beb7522f570e144bf615c07e996d443dee8729a69dce4a7d6c98e8d4a1aca87ef8d7003f83c230f3afa726ab40e52290be1c55",hex"251a6c9e46e8d62d7a31dde4a7a61c5da9b347f427f35865319f793c3b00e53728bb249af7ff8da4066641aaf1daf7b86cb3b82de3b576fa726b99555dedd689",true);
    }
    function testVector_backend_signature_28() public {
        _check(0xa0d30bd50436440e2eeff35f6bdaed546f2f7d7f141a11ef80c2542a0efc8a51,hex"55eb67d7b7238a70a7fa6f64d5dc3c826b31536da6eb344dc39a66f904f979687d916a47b2b581400b1e718bf404258540973bce1c95052dd0689f2f493be3c8",hex"f073ece5feb5dc721d4e4f540b99b5307d3f2fa351b3aa542ad4fa6a7b99c98e1d9a370d35965502f8efcdc78101b75d49e07623013dcf14438dacd1ea8b6d0b",true);
    }
    function testVector_backend_signature_29() public {
        _check(0xf0e6a8bc1d08821f859a0f5350963d122919aa7ea516877c4df503a0594c1c67,hex"c44d12c7065d812e8acf28d7cbb19f9011ecd9e9fdf281b0e6a3b5e87d22e7db2119a460ce326cdc76c45926c982fdac0e106e861edf61c5a039063f0e0e6482",hex"96bd68e6b8ea24286f1c7219808df7aac45b085412ae6ab62248ceb86a04870616990cfab9468803cc46638e5df2532a600915c3d423e964902f1bf3d060250f",true);
    }
    function testVector_backend_signature_30() public {
        _check(0x60d8208b25302588d4424d2e0596bf4a874d232b70d6c207eb0c1505fcee9f8d,hex"6d2b085e9e382ed10b69fc311a03f8641ccfff21574de0927513a49d9a688a00acb82eb93309ad1cc739ddfa33604a83776238aa0bd5ff248dbac47a17f388fb",hex"15d5bde2d4b808f78fa14be8f5951ec158e1e7bb2967908cfc7efd8d51685798652cf8e345781513ceb21191aaae2ab4338b2208715be3e95f4614a3028f99c9",true);
    }
    function testVector_backend_signature_31() public {
        _check(0x4169bc9e8476693558962ab7feb908fa86907d016435fc07b1ddb663f47eec6f,hex"6a245bf6dc698504c89a20cfded60853152b695336c28063b61c65cbd269e6b4e022cf42c2bd4a708b3f5126f16a24ad8b33ba48d0423b6efd5e6348100d8a82",hex"f3e47a3f9da9edd6c762947ec1cf1dca9c365131355cdb6e4529a5d6b0e1a459726faaedc73ceae9cc3affca9df5b8a51bdf400b74ac53f9abb2d8906b7cfd94",true);
    }
    function testVector_backend_signature_32() public {
        _check(0xc1ae050e9a6597409710c731ea8a1ebd3a99f8d4182074add8558da77c45c087,hex"d30199d74fb5a22d47b6e054e2f378cedacffcb89904a61d75d0dbd407143e6595038d9d0ae3d5c3b3d6dec9e98380651f760cc364ed819605b3ff1f24106ab9",hex"daeeb553ff0360653504ccad02c49e30900d78c440767f39e30a007ec5b7cd1a36c89b61989853d679069bd8406f0039ceb4b5d1d893eb5cd74a2875fe44d601",true);
    }
    function testVector_high_S_twin_rejected() public {
        _check(0x69a038e4ca6e8c67f96151d87f8e91bcd027bf0a69a7520bf1e5584745207155,hex"79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8",hex"eac78a87b20394063211978821427b2cbb2d1bc343306e6d0e88e70b53b7cc3ef2b5107bd65576013fa40c4d4d80f53add13c2ed0464332022bc8b57aefc0167",false);
    }
    function testVector_zero_r() public {
        _check(0x69a038e4ca6e8c67f96151d87f8e91bcd027bf0a69a7520bf1e5584745207155,hex"79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8",hex"00000000000000000000000000000000000000000000000000000000000000000d4aef8429aa89fec05bf3b2b27f0ac3dd9b19f9aae46d1b9d15d335213a3fda",false);
    }
    function testVector_r_equal_order() public {
        _check(0x69a038e4ca6e8c67f96151d87f8e91bcd027bf0a69a7520bf1e5584745207155,hex"79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8",hex"fffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd03641410d4aef8429aa89fec05bf3b2b27f0ac3dd9b19f9aae46d1b9d15d335213a3fda",false);
    }
    function testVector_zero_s() public {
        _check(0x69a038e4ca6e8c67f96151d87f8e91bcd027bf0a69a7520bf1e5584745207155,hex"79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8",hex"eac78a87b20394063211978821427b2cbb2d1bc343306e6d0e88e70b53b7cc3e0000000000000000000000000000000000000000000000000000000000000000",false);
    }
    function testVector_s_half_plus_one() public {
        _check(0x69a038e4ca6e8c67f96151d87f8e91bcd027bf0a69a7520bf1e5584745207155,hex"79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8",hex"eac78a87b20394063211978821427b2cbb2d1bc343306e6d0e88e70b53b7cc3e7fffffffffffffffffffffffffffffff5d576e7357a4501ddfe92f46681b20a1",false);
    }
    function testVector_s_equal_order() public {
        _check(0x69a038e4ca6e8c67f96151d87f8e91bcd027bf0a69a7520bf1e5584745207155,hex"79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8",hex"eac78a87b20394063211978821427b2cbb2d1bc343306e6d0e88e70b53b7cc3efffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364141",false);
    }
    function testVector_empty_key() public {
        _check(0x69a038e4ca6e8c67f96151d87f8e91bcd027bf0a69a7520bf1e5584745207155,hex"",hex"eac78a87b20394063211978821427b2cbb2d1bc343306e6d0e88e70b53b7cc3e0d4aef8429aa89fec05bf3b2b27f0ac3dd9b19f9aae46d1b9d15d335213a3fda",false);
    }
    function testVector_short_key() public {
        _check(0x69a038e4ca6e8c67f96151d87f8e91bcd027bf0a69a7520bf1e5584745207155,hex"79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4",hex"eac78a87b20394063211978821427b2cbb2d1bc343306e6d0e88e70b53b7cc3e0d4aef8429aa89fec05bf3b2b27f0ac3dd9b19f9aae46d1b9d15d335213a3fda",false);
    }
    function testVector_SEC1_prefixed_key() public {
        _check(0x69a038e4ca6e8c67f96151d87f8e91bcd027bf0a69a7520bf1e5584745207155,hex"0479be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8",hex"eac78a87b20394063211978821427b2cbb2d1bc343306e6d0e88e70b53b7cc3e0d4aef8429aa89fec05bf3b2b27f0ac3dd9b19f9aae46d1b9d15d335213a3fda",false);
    }
    function testVector_zero_point() public {
        _check(0x69a038e4ca6e8c67f96151d87f8e91bcd027bf0a69a7520bf1e5584745207155,hex"00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",hex"eac78a87b20394063211978821427b2cbb2d1bc343306e6d0e88e70b53b7cc3e0d4aef8429aa89fec05bf3b2b27f0ac3dd9b19f9aae46d1b9d15d335213a3fda",false);
    }
    function testVector_off_curve() public {
        _check(0x69a038e4ca6e8c67f96151d87f8e91bcd027bf0a69a7520bf1e5584745207155,hex"79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b9",hex"eac78a87b20394063211978821427b2cbb2d1bc343306e6d0e88e70b53b7cc3e0d4aef8429aa89fec05bf3b2b27f0ac3dd9b19f9aae46d1b9d15d335213a3fda",false);
    }
    function testVector_x_equal_field() public {
        _check(0x69a038e4ca6e8c67f96151d87f8e91bcd027bf0a69a7520bf1e5584745207155,hex"fffffffffffffffffffffffffffffffffffffffffffffffffffffffefffffc2f483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8",hex"eac78a87b20394063211978821427b2cbb2d1bc343306e6d0e88e70b53b7cc3e0d4aef8429aa89fec05bf3b2b27f0ac3dd9b19f9aae46d1b9d15d335213a3fda",false);
    }
    function testVector_y_equal_field() public {
        _check(0x69a038e4ca6e8c67f96151d87f8e91bcd027bf0a69a7520bf1e5584745207155,hex"79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798fffffffffffffffffffffffffffffffffffffffffffffffffffffffefffffc2f",hex"eac78a87b20394063211978821427b2cbb2d1bc343306e6d0e88e70b53b7cc3e0d4aef8429aa89fec05bf3b2b27f0ac3dd9b19f9aae46d1b9d15d335213a3fda",false);
    }
    function testVector_empty_signature() public {
        _check(0x69a038e4ca6e8c67f96151d87f8e91bcd027bf0a69a7520bf1e5584745207155,hex"79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8",hex"",false);
    }
    function testVector_short_signature() public {
        _check(0x69a038e4ca6e8c67f96151d87f8e91bcd027bf0a69a7520bf1e5584745207155,hex"79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8",hex"eac78a87b20394063211978821427b2cbb2d1bc343306e6d0e88e70b53b7cc3e0d4aef8429aa89fec05bf3b2b27f0ac3dd9b19f9aae46d1b9d15d335213a3f",false);
    }
    function testVector_recovery_suffix_signature() public {
        _check(0x69a038e4ca6e8c67f96151d87f8e91bcd027bf0a69a7520bf1e5584745207155,hex"79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8",hex"eac78a87b20394063211978821427b2cbb2d1bc343306e6d0e88e70b53b7cc3e0d4aef8429aa89fec05bf3b2b27f0ac3dd9b19f9aae46d1b9d15d335213a3fda1b",false);
    }
    function testVector_wrong_digest() public {
        _check(0x68a038e4ca6e8c67f96151d87f8e91bcd027bf0a69a7520bf1e5584745207155,hex"79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8",hex"eac78a87b20394063211978821427b2cbb2d1bc343306e6d0e88e70b53b7cc3e0d4aef8429aa89fec05bf3b2b27f0ac3dd9b19f9aae46d1b9d15d335213a3fda",false);
    }
    function testVector_wrong_public_key() public {
        _check(0x69a038e4ca6e8c67f96151d87f8e91bcd027bf0a69a7520bf1e5584745207155,hex"c6047f9441ed7d6d3045406e95c07cd85c778e4b8cef3ca7abac09b95c709ee51ae168fea63dc339a3c58419466ceaeef7f632653266d0e1236431a950cfe52a",hex"eac78a87b20394063211978821427b2cbb2d1bc343306e6d0e88e70b53b7cc3e0d4aef8429aa89fec05bf3b2b27f0ac3dd9b19f9aae46d1b9d15d335213a3fda",false);
    }
    function testVector_verification_point_infinity() public {
        _check(0xfffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364140,hex"79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8",hex"00000000000000000000000000000000000000000000000000000000000000010000000000000000000000000000000000000000000000000000000000000001",false);
    }
    function testUnavailableModexpDenies() public {
        vm.mockCall(address(5),bytes(""),bytes(""));
        _check(0x69a038e4ca6e8c67f96151d87f8e91bcd027bf0a69a7520bf1e5584745207155,hex"79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8",hex"eac78a87b20394063211978821427b2cbb2d1bc343306e6d0e88e70b53b7cc3e0d4aef8429aa89fec05bf3b2b27f0ac3dd9b19f9aae46d1b9d15d335213a3fda",false);
        vm.clearMockedCalls();
    }
    function testIncorrectModexpInverseDeniesAfterProbePasses() public {
        vm.mockCall(address(5),bytes(""),abi.encode(uint256(2)));
        _check(0x69a038e4ca6e8c67f96151d87f8e91bcd027bf0a69a7520bf1e5584745207155,hex"79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8",hex"eac78a87b20394063211978821427b2cbb2d1bc343306e6d0e88e70b53b7cc3e0d4aef8429aa89fec05bf3b2b27f0ac3dd9b19f9aae46d1b9d15d335213a3fda",false);
        vm.clearMockedCalls();
    }
    function testFuzzActualSignerAndHighSTwin(uint256 candidate,bytes32 digest) public {
        uint256 privateScalar=bound(candidate,1,N-1); // synthetic local fixture only
        Vm.Wallet memory wallet=vm.createWallet(privateScalar);
        uint256 x=wallet.publicKeyX;uint256 y=wallet.publicKeyY;
        (,bytes32 r,bytes32 s)=vm.sign(privateScalar,digest);
        uint256 lowS=uint256(s)>N/2 ? N-uint256(s) : uint256(s);
        bytes memory key=abi.encodePacked(x,y);
        _check(digest,key,abi.encodePacked(r,bytes32(lowS)),true);
        _check(digest,key,abi.encodePacked(r,bytes32(N-lowS)),false);
    }
    function testGas_ordinary_sha256_message() public {
        bytes memory key=hex"79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8";
        bytes memory sig=hex"eac78a87b20394063211978821427b2cbb2d1bc343306e6d0e88e70b53b7cc3e0d4aef8429aa89fec05bf3b2b27f0ac3dd9b19f9aae46d1b9d15d335213a3fda";
        uint256 initialGas=gasleft();
        bool valid=harness.verifyCalldata(0x69a038e4ca6e8c67f96151d87f8e91bcd027bf0a69a7520bf1e5584745207155,key,sig);
        uint256 used=initialGas-gasleft();
        assertTrue(valid);
        emit log_named_uint("LOCAL_VM_GAS_NOT_TARGET_CHAIN_QUALIFICATION",used);
    }
    function testGas_joint_R_and_Q_x_overflow() public {
        bytes memory key=hex"fffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd036414336b1aa62eb77c1973025cbcbea9740eed8eacdab8772268b395064453269d1d3";
        bytes memory sig=hex"00000000000000000000000000000000000000000000000000000000000000020000000000000000000000000000000000000000000000000000000000000002";
        uint256 initialGas=gasleft();
        bool valid=harness.verifyCalldata(0x0000000000000000000000000000000000000000000000000000000000000000,key,sig);
        uint256 used=initialGas-gasleft();
        assertTrue(valid);
        emit log_named_uint("LOCAL_VM_GAS_NOT_TARGET_CHAIN_QUALIFICATION",used);
    }
    function testRevertingModexpDenies() public {
        vm.mockCallRevert(address(5),bytes(""),bytes("backend unavailable fixture"));
        _check(0x69a038e4ca6e8c67f96151d87f8e91bcd027bf0a69a7520bf1e5584745207155,hex"79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8",hex"eac78a87b20394063211978821427b2cbb2d1bc343306e6d0e88e70b53b7cc3e0d4aef8429aa89fec05bf3b2b27f0ac3dd9b19f9aae46d1b9d15d335213a3fda",false);
        vm.clearMockedCalls();
    }
    function testShortModexpReturnDenies() public {
        vm.mockCall(address(5),bytes(""),new bytes(31));
        _check(0x69a038e4ca6e8c67f96151d87f8e91bcd027bf0a69a7520bf1e5584745207155,hex"79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8",hex"eac78a87b20394063211978821427b2cbb2d1bc343306e6d0e88e70b53b7cc3e0d4aef8429aa89fec05bf3b2b27f0ac3dd9b19f9aae46d1b9d15d335213a3fda",false);
        vm.clearMockedCalls();
    }
    function testLongModexpReturnDenies() public {
        vm.mockCall(address(5),bytes(""),new bytes(64));
        _check(0x69a038e4ca6e8c67f96151d87f8e91bcd027bf0a69a7520bf1e5584745207155,hex"79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8",hex"eac78a87b20394063211978821427b2cbb2d1bc343306e6d0e88e70b53b7cc3e0d4aef8429aa89fec05bf3b2b27f0ac3dd9b19f9aae46d1b9d15d335213a3fda",false);
        vm.clearMockedCalls();
    }
    function testIncorrectModexpProbeDenies() public {
        vm.mockCall(address(5),bytes(""),abi.encode(uint256(1)));
        _check(0x69a038e4ca6e8c67f96151d87f8e91bcd027bf0a69a7520bf1e5584745207155,hex"79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8",hex"eac78a87b20394063211978821427b2cbb2d1bc343306e6d0e88e70b53b7cc3e0d4aef8429aa89fec05bf3b2b27f0ac3dd9b19f9aae46d1b9d15d335213a3fda",false);
        vm.clearMockedCalls();
    }
}
