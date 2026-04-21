# 🚀 Aarogya AI — Deployment Guide (Step by Step)

## What You Need
- A GitHub account → https://github.com
- A Render account → https://render.com
- That's it! Both are FREE.

---

## PART 1 — Upload to GitHub (5 minutes)

### Step 1 — Download & Install Git
→ https://git-scm.com/downloads
→ Install with default settings

### Step 2 — Create GitHub Repository
1. Go to https://github.com → Login
2. Click the **"+"** button (top right) → **"New repository"**
3. Name it: `Aarogya-AI`
4. Keep it **Public**
5. Click **"Create repository"**

### Step 3 — Open Terminal / Command Prompt
Navigate to your project folder:
```
cd path/to/Aarogya_AI
```

### Step 4 — Push Your Code
Run these commands one by one:
```
git init
git add .
git commit -m "Aarogya AI - Initial Deploy"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/Aarogya-AI.git
git push -u origin main
```
(Replace YOUR_USERNAME with your GitHub username)

✅ Your code is now on GitHub!

---

## PART 2 — Deploy on Render (5 minutes)

### Step 1 — Create Render Account
→ Go to https://render.com
→ Click "Get Started" → Sign up with GitHub

### Step 2 — Create Web Service
1. Click **"New +"** → **"Web Service"**
2. Click **"Connect a repository"**
3. Select your **Aarogya-AI** repo
4. Click **"Connect"**

### Step 3 — Configure Settings
Fill in these exact values:

| Field | Value |
|-------|-------|
| Name | aarogya-ai |
| Region | Singapore (closest to India) |
| Branch | main |
| Runtime | Python 3 |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn app:app` |
| Instance Type | Free |

### Step 4 — Add Environment Variable
Scroll down to **"Environment Variables"** → Click **"Add Environment Variable"**:
- Key: `SECRET_KEY`
- Value: `aarogya-secret-2024-xK9mP2qR`

### Step 5 — Deploy!
Click **"Create Web Service"**

⏳ Wait 3-5 minutes for deployment...

✅ Your app will be live at:
**https://aarogya-ai.onrender.com**

---

## PART 3 — Test Your Live App

1. Open the URL in browser
2. Login as Admin: `admin@aarogya.ai` / `Admin@123`
3. Login as Doctor: `doctor@aarogya.ai` / `Doctor@123`
4. Register a new patient and test disease prediction

---

## Common Errors & Fixes

### "Application Error" on Render
→ Go to Render dashboard → Click your service → Click "Logs"
→ Look for the error message

### "Module not found" error
→ Make sure all libraries are in requirements.txt

### App is slow on first load
→ Normal! Free tier "sleeps" after 15 min inactivity
→ First visit wakes it up (takes ~30 seconds)

---

## 🎓 For College Demo

Show these things:
1. Open your live URL on phone AND laptop at same time
2. Show GitHub repo → "my code is version controlled on cloud"
3. Show Render dashboard → "deployed on cloud server"
4. Do a live disease prediction
5. Show blockchain audit trail as admin

Good luck! 🎉
