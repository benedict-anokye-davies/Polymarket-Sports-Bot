# Session Walkthrough: Connection Issues Fix

## Summary

Fixed two critical issues preventing the Polymarket-Kalshi-Bot from working:
1. **CORS Configuration Error** - Malformed URLs in Railway environment variables
2. **RSA Key Parsing Error** - Private keys getting corrupted during copy/paste

---

## Issue 1: CORS Configuration

### Problem
The registration page showed "Unable to connect to server" error. Investigation revealed that CORS preflight requests to `/api/v1/auth/register` were returning 400 errors.

### Root Cause
The `CORS_ALLOWED_ORIGINS` environment variable on Railway contained **malformed URLs**:
```
https://44bd3cttps://polymarket-sports-bot-9ndj.vercel.app  ❌ Corrupted
```

### Fix
Updated the Railway environment variable with correct URLs:
```
http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173,
https://polymarket-sports-bot.netlify.app,https://polymarket-sports-bot.vercel.app,
https://polymarket-sports-bot-9ndj.vercel.app,https://polymarket-sports-bot-7j2h.vercel.app,
https://polymarket-sports-bot-ctjt.vercel.app,https://polymarket-sports-bot-zz8c.vercel.app,
https://polymarket-sports-bot.pages.dev,https://44bd3c47.polymarket-sports-bot.pages.dev,
https://polymarket-sports-bot-production.up.railway.app
```

### Verification
- Registration page now loads without connection errors
- Backend responds with proper HTTP status codes instead of CORS failures

---

## Issue 2: RSA Key Parsing

### Problem
Users entering Kalshi RSA private keys received:
```
Error: Invalid RSA private key format. MalformedFraming
```

### Root Cause
RSA keys pasted from files or JSON could have:
- Escaped newlines (`\n` as literal text instead of line breaks)
- Missing line breaks (key on single line)
- Windows line endings (`\r\n`)

### Fix
Added `normalize_pem_key()` method to [kalshi_client.py](file:///c:/Users/Nxiss/OneDrive/Desktop/Polymarket-Kalshi-Bot/src/services/kalshi_client.py):

```python
@staticmethod
def normalize_pem_key(private_key_pem: str) -> str:
    """
    Normalize a PEM private key to ensure proper format.
    Handles:
    - Escaped newlines (\\n as literal text)
    - Missing newlines (key pasted as single line)
    - Extra whitespace
    """
    key = private_key_pem.strip()
    
    # Replace literal \n with actual newlines
    key = key.replace('\\n', '\n')
    key = key.replace('\r\n', '\n')
    
    # If key is on one line, restructure into 64-char lines
    if '-----BEGIN' in key and '-----END' in key:
        lines = key.split('\n')
        if len(lines) <= 3:
            # Extract and reformat
            match = re.match(
                r'(-----BEGIN [A-Z ]+-----)(.+)(-----END [A-Z ]+-----)',
                key.replace('\n', ''), re.DOTALL
            )
            if match:
                header, body, footer = match.groups()
                body_lines = [body[i:i+64] for i in range(0, len(body), 64)]
                key = header + '\n' + '\n'.join(body_lines) + '\n' + footer
    
    return key.strip() + '\n'
```

Added to both:
- `KalshiAuthenticator._normalize_pem_key()` 
- `KalshiClient.normalize_pem_key()`

Updated `validate_rsa_key()` and `KalshiAuthenticator.__init__()` to use normalization.

### Deployment
```bash
git commit -m "Fix RSA key parsing: add normalize_pem_key to handle various paste formats"
git push  # Railway auto-deploys from master
```

---

## Files Modified

| File | Changes |
|------|---------|
| [kalshi_client.py](file:///c:/Users/Nxiss/OneDrive/Desktop/Polymarket-Kalshi-Bot/src/services/kalshi_client.py) | Added `normalize_pem_key()` methods to handle RSA key formats |

## Environment Changes

| Service | Variable | Action |
|---------|----------|--------|
| Railway | `CORS_ALLOWED_ORIGINS` | Fixed malformed URLs |

---

## Verification Steps

1. **CORS Fix**: Navigate to registration page - no "Unable to connect to server" error
2. **RSA Key Fix**: Paste RSA key in onboarding - accepts various formats without error

## Next Steps for User

1. Wait ~2 minutes for Railway deployment
2. Go to https://44bd3c47.polymarket-sports-bot.pages.dev/onboarding
3. Enter Kalshi API Key and RSA Private Key
4. Complete onboarding flow
