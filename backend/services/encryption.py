import logging
import os
import hashlib
import secrets
from typing import Optional, Tuple
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from backend.config import settings

logger = logging.getLogger(__name__)

class TokenVault:
    """Encrypted token storage for calendar accounts and sensitive data"""
    
    def __init__(self, master_key: Optional[bytes] = None):
        if master_key:
            self.master_key = master_key
        else:
            # Derive from settings.encryption_key + device fingerprint
            self.master_key = self._derive_master_key()
    
    def _derive_master_key(self) -> bytes:
        """Derive master key from settings + device fingerprint"""
        # In production, this would use a hardware-backed key or secure enclave
        key_material = settings.encryption_key.encode() if settings.encryption_key else b'default-dev-key-change-in-production'
        
        # Add device fingerprint (hostname, etc.)
        import socket
        fingerprint = socket.gethostname().encode()
        key_material += hashlib.sha256(fingerprint).digest()[:16]
        
        # Use Scrypt for key derivation
        kdf = Scrypt(
            salt=b'helios-salt-v1',  # In production, use per-user random salt
            length=32,
            n=16384,
            r=8,
            p=1
        )
        return kdf.derive(key_material)
    
    def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext and return base64 encoded ciphertext"""
        if not plaintext:
            return ""
        
        # Generate random nonce (12 bytes for AES-GCM)
        nonce = secrets.token_bytes(12)
        
        # Encrypt
        aesgcm = AESGCM(self.master_key)
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
        
        # Combine nonce + ciphertext and base64 encode
        combined = nonce + ciphertext
        import base64
        return base64.b64encode(combined).decode()
    
    def decrypt(self, encrypted: str) -> str:
        """Decrypt base64 encoded ciphertext"""
        if not encrypted:
            return ""
        
        try:
            import base64
            combined = base64.b64decode(encrypted.encode())
            
            # Extract nonce (first 12 bytes) and ciphertext
            nonce = combined[:12]
            ciphertext = combined[12:]
            
            # Decrypt
            aesgcm = AESGCM(self.master_key)
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
            
            return plaintext.decode()
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise ValueError("Decryption failed - wrong key or corrupted data")
    
    def rotate_key(self, new_master_key: bytes):
        """Rotate master key - re-encrypt all stored tokens"""
        old_key = self.master_key
        self.master_key = new_master_key
        
        # In production, you'd iterate through all stored tokens and re-encrypt
        logger.warning("Key rotation initiated - manual re-encryption of stored tokens required")


class DatabaseEncryption:
    """Application-level encryption for sensitive database columns"""
    
    def __init__(self, vault: TokenVault):
        self.vault = vault
    
    def encrypt_value(self, value: float) -> str:
        """Encrypt a numeric value"""
        return self.vault.encrypt(str(value))
    
    def decrypt_value(self, encrypted: str) -> float:
        """Decrypt a numeric value"""
        return float(self.vault.decrypt(encrypted))
    
    def encrypt_json(self, data: dict) -> str:
        """Encrypt JSON data"""
        import json
        return self.vault.encrypt(json.dumps(data))
    
    def decrypt_json(self, encrypted: str) -> dict:
        """Decrypt JSON data"""
        import json
        return json.loads(self.vault.decrypt(encrypted))


# Row-level encryption for sensor readings
class SensorDataEncryption:
    """Encrypt sensitive sensor reading fields"""
    
    def __init__(self, db_encryption: DatabaseEncryption):
        self.db_encryption = db_encryption
    
    def encrypt_reading(self, reading: dict) -> dict:
        """Encrypt sensitive fields of a sensor reading"""
        encrypted = reading.copy()
        
        # Encrypt value and raw_json
        if 'value' in encrypted and encrypted['value'] is not None:
            encrypted['value'] = self.db_encryption.encrypt_value(encrypted['value'])
        
        if 'raw_json' in encrypted and encrypted['raw_json'] is not None:
            encrypted['raw_json'] = self.db_encryption.encrypt_json(encrypted['raw_json'])
        
        return encrypted
    
    def decrypt_reading(self, encrypted: dict) -> dict:
        """Decrypt sensitive fields of a sensor reading"""
        decrypted = encrypted.copy()
        
        if 'value' in decrypted and isinstance(decrypted['value'], str):
            try:
                decrypted['value'] = self.db_encryption.decrypt_value(decrypted['value'])
            except:
                pass  # Not encrypted
        
        if 'raw_json' in decrypted and isinstance(decrypted['raw_json'], str):
            try:
                decrypted['raw_json'] = self.db_encryption.decrypt_json(decrypted['raw_json'])
            except:
                pass  # Not encrypted
        
        return decrypted


# Backup encryption
class BackupEncryption:
    """Encrypt entire database backups"""
    
    def __init__(self, vault: TokenVault):
        self.vault = vault
    
    async def encrypt_backup(self, db_path: str, output_path: str, password: str) -> bool:
        """Encrypt SQLite database file using user password"""
        import subprocess
        
        try:
            # Derive key from password
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b'helios-backup-salt',  # Should be random per backup
                iterations=100000
            )
            key = kdf.derive(password.encode())
            
            # Use SQLCipher or encrypt file with AES-GCM
            # For simplicity, encrypt the file directly
            with open(db_path, 'rb') as f:
                data = f.read()
            
            nonce = secrets.token_bytes(12)
            aesgcm = AESGCM(key)
            ciphertext = aesgcm.encrypt(nonce, data, None)
            
            # Write encrypted file
            with open(output_path, 'wb') as f:
                f.write(nonce + ciphertext)
            
            logger.info(f"Backup encrypted: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Backup encryption failed: {e}")
            return False
    
    async def decrypt_backup(self, encrypted_path: str, output_path: str, password: str) -> bool:
        """Decrypt backup file"""
        import subprocess
        
        try:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b'helios-backup-salt',
                iterations=100000
            )
            key = kdf.derive(password.encode())
            
            with open(encrypted_path, 'rb') as f:
                data = f.read()
            
            nonce = data[:12]
            ciphertext = data[12:]
            
            aesgcm = AESGCM(key)
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
            
            with open(output_path, 'wb') as f:
                f.write(plaintext)
            
            logger.info(f"Backup decrypted: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Backup decryption failed: {e}")
            return False