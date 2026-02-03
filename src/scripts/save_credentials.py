
import os
# FORCE DATABASE TO test_local.db
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_local.db"

import asyncio
import logging
from sqlalchemy import select
from src.db.database import async_session_factory
from src.models.user import User
from src.models.polymarket_account import PolymarketAccount
from src.core.encryption import encrypt_credential

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# CREDENTIALS FROM USER
API_KEY = "813faefe-becc-4647-807a-295dcf69fcad"
PRIVATE_KEY = """-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEAuYNtYEs6cA+CftxzyYI5nJCKuYodXxxhVydablc6tdlbvgRl
IxGSnh5udAXqPYVyDxA643HAIaQZ7DtXmgR1jrRzyDnEfBTdXFKnKNaxr7aSA+/s
FB6XY45c7Tw0F96D5UpHkUMzRvEbhxE6eph0OCM0FlaqC0WUkFtUdNIBcCeb7sQq
T6b/tPVHWY/IU4/QhWF3j+2+rNVpKVFTwAxPZpKHHsb6PMIKqV8gRCPvmJPXIpaL
S72pCuaFzqAXzmgYKYxdxLUnrzrDbYqF9jE0bi5i3+ybGzt67zQK/YYOq7cS/91p
TNXCX0vT3voBw7u04XHK2SL9BljBixRHRKIlzwIDAQABAoIBAByv+L1/1KEYnObu
Q0+BflQ6O+GWPJWFJ35ZPRA8F/2gB6JaPqOOJ5yg+xahBYiO9sTijyC16e6p2EJi
KNlN4Dn5qL/pQvunJFYPB/92N9MCyhCmzNyNoH6KOM+M1EdupvnRo0CQ4kCRr16T
KPZlVe+KbhcYPsJwd5ldLjHEeel0SsQvTkO5lVYrfE2AEn0T1/NfyK2uY4YIOaqe
LcokQ+rhC+9gw9z3gvIwNZeQheD+aTnN7Ow2yuCjzpu3b4b3zeuTA0xRWX14qS27
wD6pX1EhAg4gDTm1CDgyvKFvUpKybqS/xqY/lQBEtRq2dUJxxzyChiXZ8dA2ikLW
zqEwyzkCgYEAwub0Ji8n3V0XwdjngUElYdHMwxIMN3y+a3ZY0KGPMTGo3gwy7xNW
irTTLFAJN3+ax1H0eYuIzmfe519Yt9r0pE+YDHk4sZw9v88iXEF6Ci0CaDJKPDoV
hcuzcqqs65/CzOpwfcDBBWw3RI4g6A/IIf/+BSlO8PipTroiMIhEmlcCgYEA86sE
aDuHZ8O+Y5DW9XcE2P259mv+uUfqpEGreIOq0y4bIyhCWIpsJWrf2QglPc/wLWBs
WQGmfCcPd/M5gDK4M33ICiDeT8i+oVI5R8sHq4YchyWrE5jvcqNvGA90fLuTcU/h
NU53JU2rwh2+t35ZJz1N911ADkW6mf9173s/FUkCgYAv7kY6obwnBz7RcDs2oUPF
M6gsjOKuPqJBoUAkRqcFTRYfTVa1Tscoo2GPczthB6OTwwbhYTxKrma19c/GnzUs
t1pILwOPQkI5SoJDt+KAYCNIZp21A//JAJhn6atO4uIwLLNvaZjOcZeB54YWK9Nm
8SKSOF9uiWhxsPq5frmITwKBgQDfEQRr13NSDuRQidv/wwFxFHYVnTAHtkqcLHIp
VYAg6+hz+vshyzbN2lUqfkZ5m86n+8m0gcpDhg6nJMbTEZuHp/JlM0nRiFjbnkZJ
7xgKci/TmSxQOIWcUPn28M8XETEdXp8xCbAROlWu00Qw/z3mqjyh44AskLEPIcp5
fj514QKBgQCehv55lkweFU7rcH3obsFLn7Jmu+v29cs56Cr3Jum7yPiFQj4jRzqT
3gs2DfzbuFymCew5CIvtkzf6fQq1f5n4aQKGCrtsBWO2C1XI3+y7LHo2fPvohpP3
ZvNh6+wUMv2j8hQ9TLSakgflUG00Gv9ULivPmYszqSHeMP1HzL9EaA==
-----END RSA PRIVATE KEY-----"""

async def save_credentials():
    async with async_session_factory() as db:
        # 1. Get User (Pick the first one, likely dev_user)
        result = await db.execute(select(User))
        users = result.scalars().all()
        if not users:
            logger.error("No users found!")
            return
        
        user = users[0]
        logger.info(f"Updating credentials for user: {user.username} ({user.id})")
        
        # 2. Get or Create Account
        result = await db.execute(select(PolymarketAccount).where(PolymarketAccount.user_id == user.id))
        account = result.scalar_one_or_none()
        
        if not account:
            logger.info("Creating new account record...")
            account = PolymarketAccount(user_id=user.id)
            db.add(account)
        
        # 3. Update with Kalshi Credentials
        account.platform = "kalshi"
        account.api_key_encrypted = encrypt_credential(API_KEY)  # Kalshi KID
        account.private_key_encrypted = encrypt_credential(PRIVATE_KEY) # Kalshi RSA Key
        account.is_connected = True
        account.environment = "production"
        
        # Clear others to avoid confusion
        account.api_secret_encrypted = None
        account.api_passphrase_encrypted = None
        
        await db.commit()
        logger.info("✅ Credentials saved successfully!")

if __name__ == "__main__":
    asyncio.run(save_credentials())
