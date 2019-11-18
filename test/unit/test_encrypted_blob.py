from pisa import c_logger
from pisa.encrypted_blob import EncryptedBlob
from test.unit.conftest import get_random_value_hex

c_logger.disabled = True


def test_init_encrypted_blob():
    # No much to test here, basically that the object is properly created
    data = get_random_value_hex(64)
    assert EncryptedBlob(data).data == data


def test_init_encrypted_blob_wrong_cipher():
    try:
        EncryptedBlob(get_random_value_hex(64), cipher="")
        assert False

    except ValueError:
        assert True


def test_init_encrypted_blob_wrong_hash_function():
    try:
        EncryptedBlob(get_random_value_hex(64), hash_function="")
        assert False

    except ValueError:
        assert True


def test_equal():
    data = get_random_value_hex(64)
    e_blob1 = EncryptedBlob(data)
    e_blob2 = EncryptedBlob(data)

    assert e_blob1 == e_blob2 and id(e_blob1) != id(e_blob2)
