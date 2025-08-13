# 🚀 Render Deployment Guide

## Pre-Deployment Checklist

### ✅ **Files Ready for Deployment:**
- `render.yaml` - Render configuration
- `start_render.py` - Custom startup script
- `deploy_config.py` - Deployment environment setup
- `requirements.txt` - All dependencies included
- `Procfile` - Process configuration
- `.env.example` - Environment variables template

### ✅ **Key Features Configured:**
- **Port Configuration**: Automatically uses Render's PORT environment variable
- **Selenium Handling**: Gracefully disabled on Render (DISABLE_SELENIUM=true)
- **Database Initialization**: Automatic SQLite database setup
- **Agent Initialization**: Robust error handling for missing agents
- **Environment Variables**: Production-ready configuration

## 🔧 **Environment Variables to Set in Render:**

### **Required:**
```
FLASK_ENV=production
DISABLE_SELENIUM=true
PORT=10000
```

### **Optional (for enhanced functionality):**
```
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

### **Agent URLs (configure in admin panel after deployment):**
```
DOWNLOADHUB_URL=https://hdhub4u.build/
MOVIERULZ_URL=https://www.5movierulz.pizza/
MOVIEZWAP_URL=https://www.moviezwap.blue/
MOVIES4U_URL=https://movies4u.bh/
```

## 📋 **Deployment Steps:**

1. **Connect Repository to Render**
   - Go to Render Dashboard
   - Click "New +" → "Web Service"
   - Connect your GitHub repository

2. **Configure Service**
   - **Name**: movie-agent
   - **Environment**: Python
   - **Build Command**: `pip install -r requirements.txt && mkdir -p data && mkdir -p config`
   - **Start Command**: `python start_render.py`

3. **Set Environment Variables**
   - Add the required environment variables listed above
   - Set DISABLE_SELENIUM=true to avoid Chrome/Selenium issues

4. **Deploy**
   - Click "Create Web Service"
   - Wait for deployment to complete

## 🔍 **Post-Deployment Verification:**

### **Check These URLs:**
- `https://your-app.onrender.com/` - Main interface
- `https://your-app.onrender.com/api` - API interface
- `https://your-app.onrender.com/admin` - Admin panel

### **Test Functionality:**
1. **Chat Interface**: Try searching for movies
2. **Admin Panel**: Configure agent URLs
3. **Movie Search**: Test different agents
4. **Link Extraction**: Verify download links work

## ⚠️ **Known Limitations on Render:**

1. **Selenium Disabled**: Movies4U agent won't work (requires Chrome)
2. **Cold Starts**: First request may be slow
3. **File Storage**: SQLite database resets on redeploy
4. **Memory Limits**: Free tier has 512MB RAM limit

## 🐛 **Troubleshooting:**

### **If deployment fails:**
- Check build logs for missing dependencies
- Verify environment variables are set
- Ensure all files are committed to Git

### **If app crashes:**
- Check application logs in Render dashboard
- Verify database initialization
- Check agent URL accessibility

### **If features don't work:**
- Verify environment variables
- Check admin panel configuration
- Test individual agents

## 🎯 **Optimization Tips:**

1. **Keep Service Warm**: Use a service like UptimeRobot to ping your app
2. **Monitor Logs**: Regularly check Render logs for errors
3. **Update Dependencies**: Keep requirements.txt updated
4. **Configure Agents**: Set up working URLs in admin panel

## 📞 **Support:**

If you encounter issues:
1. Check Render logs first
2. Verify environment variables
3. Test locally with same configuration
4. Check agent URL accessibility

---

**✅ Your Movie Agent is ready for Render deployment!**