# 🌐 SportsQuantx.com - Complete Setup Guide

**Domain:** SportsQuantx.com  
**Status:** Ready for Configuration  
**Date:** January 30, 2026

---

## ✅ What I Just Did (Code Changes)

### 1. Updated CORS Configuration ✅
**File:** `.env.example`
- Added `https://SportsQuantx.com` and `https://www.SportsQuantx.com` to CORS_ALLOWED_ORIGINS
- This allows the frontend to communicate with the backend

---

## 🚀 What YOU Need to Do (3 Steps)

Since I cannot access your accounts, you need to do these 3 things:

### **STEP 1: Add DNS Records** (5 minutes)

**Log into your domain registrar** (GoDaddy, Namecheap, Cloudflare, etc.)

**Add these DNS records:**

```
Type: A
Name: @ (or leave blank)
Value: 76.76.21.21
TTL: 600
```

```
Type: CNAME
Name: www
Value: cname.vercel-dns.com
TTL: 600
```

```
Type: A
Name: api
Value: (You'll get this from Railway in Step 2)
TTL: 600
```

---

### **STEP 2: Configure Railway** (5 minutes)

**Go to:** https://railway.app/dashboard

1. Click your project
2. Click **"Settings"** tab
3. Click **"Custom Domain"**
4. Enter: `api.SportsQuantx.com`
5. Click **"Add Domain"**
6. Railway will show you an **IP address** - copy it!
7. Go back to Step 1 and add that IP to your DNS

**Also set this environment variable in Railway:**
```
CORS_ALLOWED_ORIGINS=https://SportsQuantx.com,https://www.SportsQuantx.com
```

---

### **STEP 3: Configure Vercel** (5 minutes)

**Go to:** https://vercel.com/dashboard

1. Click your project
2. Click **"Settings"** → **"Domains"**
3. Add: `SportsQuantx.com`
4. Add: `www.SportsQuantx.com`
5. Vercel will verify automatically

**Also update this environment variable:**
```
VITE_API_URL=https://api.SportsQuantx.com
```

---

## ⏱️ Timeline

| Step | Action | Time |
|------|--------|------|
| 1 | Add DNS records | 5 mins |
| 2 | Configure Railway | 5 mins |
| 3 | Configure Vercel | 5 mins |
| 4 | Wait for propagation | 10-15 mins |
| **Total** | | **25-30 mins** |

---

## 🔍 Verification

After 15-20 minutes, test:

```bash
# Test backend
curl https://api.SportsQuantx.com/api/health/quick

# Should return:
{"status": "healthy", "timestamp": "..."}
```

Open browser:
- `https://SportsQuantx.com` → Should show login page
- `https://api.SportsQuantx.com/docs` → Should show API docs

---

## 🎯 Final URLs

| Service | URL | Status |
|---------|-----|--------|
| **Frontend** | https://SportsQuantx.com | ⏳ Pending your setup |
| **API** | https://api.SportsQuantx.com | ⏳ Pending your setup |
| **Health** | https://api.SportsQuantx.com/api/health/quick | ⏳ Pending your setup |

---

## 🆘 If You Get Stuck

**DNS not working?**
- Wait 15-30 minutes (DNS takes time)
- Check with: `dig SportsQuantx.com`

**Railway domain not verifying?**
- Make sure DNS record matches Railway's IP exactly
- Try removing and re-adding the domain

**Vercel domain not working?**
- Make sure the A record is `76.76.21.21`
- Try www.SportsQuantx.com instead

---

## 🎉 After Setup

Once everything is working:
1. ✅ Test login at https://SportsQuantx.com
2. ✅ Run 48-hour paper trading test
3. ✅ Enable live trading
4. ✅ Start making money! 💰

---

**Need help?** Check the screenshots in DEPLOYMENT_GUIDE.md or ask!

**Status:** Code ready, waiting for your DNS/Railway/Vercel configuration
