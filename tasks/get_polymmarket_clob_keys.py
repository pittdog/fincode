from py_clob_client.client import ClobClient
import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Load your private key securely from env var
private_key = os.getenv("POLYMARKET_PRIVATE_KEY")

if not private_key:
    print("Error: POLYMARKET_PRIVATE_KEY environment variable is not set.")
    sys.exit(1)

# Debug: Masked key length check
print(f"Private Key loaded (length: {len(private_key)})")
print(f"Initializing client for: {private_key[:6]}...{private_key[-4:]}")

try:
    client = ClobClient(
        host="https://clob.polymarket.com",
        key=private_key,
        chain_id=137  # Polygon Mainnet
    )

    # Derive or create API credentials
    print("Deriving/Creating API credentials (this may take a moment)...")
    api_creds = client.create_or_derive_api_creds()

    print("\n" + "="*40)
    print("POLYMARKET CLOB API CREDENTIALS")
    print("="*40)
    print(f"API Key:    {api_creds.api_key}")
    print(f"Secret:     {api_creds.api_secret}")
    print(f"Passphrase: {api_creds.api_passphrase}")
    print("="*40)
    print("\nIMPORTANT: Save these credentials securely. They are derived from your private key.")

except Exception as e:
    print(f"\nError occurred: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)