from utils.password_hashing import verify_password


def test_verify_password_rejects_invalid_bcrypt_salt():
    assert verify_password("changeme", "not-a-bcrypt-hash") is False


def test_verify_password_rejects_empty_hash():
    assert verify_password("changeme", "") is False
