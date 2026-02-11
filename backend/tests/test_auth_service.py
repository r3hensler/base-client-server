import pytest
from app.services.auth import (
    hash_password,
    verify_password,
    validate_password_strength,
    create_access_token,
    decode_access_token,
    generate_refresh_token,
)
import uuid
import jwt as pyjwt


class TestPasswordHashing:
    def test_hash_and_verify(self):
        hashed = hash_password("mysecretpass")
        assert hashed != "mysecretpass"
        assert verify_password("mysecretpass", hashed)

    def test_wrong_password_fails(self):
        hashed = hash_password("correct")
        assert not verify_password("wrong", hashed)


class TestPasswordStrength:
    def test_valid_password(self):
        # Should not raise
        validate_password_strength("ValidPass123!")

    def test_too_short(self):
        with pytest.raises(ValueError, match="at least 8 characters"):
            validate_password_strength("Abc1!")

    def test_too_long(self):
        with pytest.raises(ValueError, match="not exceed 128 characters"):
            validate_password_strength("A1!" + "a" * 130)

    def test_no_uppercase(self):
        with pytest.raises(ValueError, match="uppercase"):
            validate_password_strength("password123!")

    def test_no_lowercase(self):
        with pytest.raises(ValueError, match="lowercase"):
            validate_password_strength("PASSWORD123!")

    def test_no_digit(self):
        with pytest.raises(ValueError, match="digit"):
            validate_password_strength("Password!")

    def test_no_special_char(self):
        with pytest.raises(ValueError, match="special character"):
            validate_password_strength("Password123")


class TestAccessToken:
    def test_create_and_decode(self):
        user_id = uuid.uuid4()
        token = create_access_token(user_id)
        payload = decode_access_token(token)
        assert payload["sub"] == str(user_id)
        assert payload["type"] == "access"
        assert payload["iss"] == "base-client-server"
        assert payload["aud"] == "base-client-server-api"
        assert "iat" in payload
        assert "exp" in payload

    def test_invalid_token_raises(self):
        with pytest.raises(pyjwt.PyJWTError):
            decode_access_token("garbage.token.here")

    def test_wrong_issuer_raises(self):
        # Create token with different issuer
        user_id = uuid.uuid4()
        from datetime import UTC, datetime, timedelta
        from app.config import settings

        payload = {
            "sub": str(user_id),
            "exp": datetime.now(UTC) + timedelta(minutes=15),
            "iss": "wrong-issuer",
            "aud": "base-client-server-api",
            "type": "access",
        }
        token = pyjwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")
        with pytest.raises(pyjwt.InvalidIssuerError):
            decode_access_token(token)


class TestRefreshToken:
    def test_generates_unique_tokens(self):
        raw1, hash1 = generate_refresh_token()
        raw2, hash2 = generate_refresh_token()
        assert raw1 != raw2
        assert hash1 != hash2

    def test_hash_is_deterministic(self):
        import hashlib

        raw, expected_hash = generate_refresh_token()
        actual_hash = hashlib.sha256(raw.encode()).hexdigest()
        assert actual_hash == expected_hash
