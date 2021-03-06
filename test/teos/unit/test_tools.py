from teos.tools import can_connect_to_bitcoind, in_correct_network, bitcoin_cli
from common.tools import check_sha256_hex_format
from test.teos.unit.conftest import bitcoind_connect_params


def test_in_correct_network(run_bitcoind):
    # The simulator runs as if it was regtest, so every other network should fail
    assert in_correct_network(bitcoind_connect_params, "mainnet") is False
    assert in_correct_network(bitcoind_connect_params, "testnet") is False
    assert in_correct_network(bitcoind_connect_params, "regtest") is True


def test_can_connect_to_bitcoind():
    assert can_connect_to_bitcoind(bitcoind_connect_params) is True


# def test_can_connect_to_bitcoind_bitcoin_not_running():
#     # Kill the simulator thread and test the check fails
#     bitcoind_process.kill()
#     assert can_connect_to_bitcoind() is False


def test_bitcoin_cli():
    try:
        bitcoin_cli(bitcoind_connect_params).help()
        assert True

    except Exception:
        assert False


def test_check_sha256_hex_format():
    assert check_sha256_hex_format(None) is False
    assert check_sha256_hex_format("") is False
    assert (
        check_sha256_hex_format(0x0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF) is False
    )  # wrong type
    assert (
        check_sha256_hex_format("abcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcd") is True
    )  # lowercase
    assert (
        check_sha256_hex_format("ABCDEFABCDEFABCDEFABCDEFABCDEFABCDEFABCDEFABCDEFABCDEFABCDEFABCD") is True
    )  # uppercase
    assert (
        check_sha256_hex_format("0123456789abcdef0123456789ABCDEF0123456789abcdef0123456789ABCDEF") is True
    )  # mixed case
    assert (
        check_sha256_hex_format("0123456789012345678901234567890123456789012345678901234567890123") is True
    )  # only nums
    assert (
        check_sha256_hex_format("0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdf") is False
    )  # too short
    assert (
        check_sha256_hex_format("0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef0") is False
    )  # too long
    assert (
        check_sha256_hex_format("g123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef") is False
    )  # non-hex
