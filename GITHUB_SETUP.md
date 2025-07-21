# GitHub Setup Instructions

## Issue: Password Authentication No Longer Supported

GitHub removed support for password authentication on August 13, 2021. You need to use a Personal Access Token (PAT) instead.

## Steps to Create Personal Access Token:

1. **Go to GitHub Settings:**
   - Visit: https://github.com/settings/tokens
   - Or: GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)

2. **Generate New Token:**
   - Click "Generate new token (classic)"
   - Give it a descriptive name: "Movie-Agent-Repo"
   - Set expiration (recommended: 90 days or custom)
   - Select scopes:
     - ✅ `repo` (Full control of private repositories)
     - ✅ `workflow` (Update GitHub Action workflows)

3. **Copy the Token:**
   - **IMPORTANT:** Copy the token immediately - you won't see it again!
   - It will look like: `ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

## Push to GitHub with Token:

Once you have your token, run these commands:

```bash
cd Desktop/Movie_Agent/movie_web_interface

# Add remote with your username and token
git remote add origin https://guruvamsi061:YOUR_TOKEN_HERE@github.com/guruvamsi061/Movie-Agent.git

# Push to GitHub
git push -u origin main
```

## Alternative: Create Repository First

If the repository doesn't exist on GitHub:

1. Go to https://github.com/new
2. Repository name: `Movie-Agent`
3. Make it Public or Private
4. Don't initialize with README (we already have one)
5. Click "Create repository"

Then use the commands above to push your code.

## Current Status:
✅ Local repository created and committed
✅ All files ready to push
⏳ Waiting for Personal Access Token to push to GitHub