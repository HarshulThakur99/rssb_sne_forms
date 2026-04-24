# Fixing HTTP 413 "Request Entity Too Large" Error

## Problem Description

Users intermittently receive an **HTTP 413 "Request entity too large nginx/1.26.3"** error when submitting SNE forms with photo uploads. This occurs when the uploaded file size exceeds nginx's default limit (1MB).

## Root Cause

The error happens at the **nginx layer** before the request reaches Flask. By default:
- nginx has a `client_max_body_size` limit of **1MB**
- Our Flask app allows uploads up to **16MB** (`MAX_CONTENT_LENGTH` in config.py)
- Form photos can be **2MB or larger**, exceeding nginx's limit

## Solution Overview

This has been fixed with a **three-layer approach**:

1. ✅ **Client-side validation** - JavaScript prevents users from selecting files > 2MB
2. ✅ **Flask error handling** - Catches 413 errors with user-friendly messages
3. ⚠️ **nginx configuration** - **YOU MUST UPDATE** your nginx config to increase limits

---

## IMMEDIATE ACTION REQUIRED: Update Nginx Configuration

### Step 1: Locate Your Nginx Configuration

Your nginx configuration file is typically located at:
```bash
/etc/nginx/sites-available/rssb_sne_forms
# or
/etc/nginx/nginx.conf
```

### Step 2: Add/Update `client_max_body_size`

Add this line inside your `server {}` block(s):

```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    # CRITICAL: Increase upload limit to 20MB
    client_max_body_size 20M;
    
    # ... rest of your configuration
}
```

**Important:** Add this to **BOTH** HTTP (port 80) and HTTPS (port 443) server blocks if using SSL.

### Step 3: Complete nginx Configuration

For a complete, production-ready nginx configuration, use the provided template:

```bash
# Copy the template to nginx sites-available
sudo cp nginx_config_snippet.conf /etc/nginx/sites-available/rssb_sne_forms

# Edit and customize (update domain, paths, etc.)
sudo nano /etc/nginx/sites-available/rssb_sne_forms

# Create symlink to enable the site
sudo ln -sf /etc/nginx/sites-available/rssb_sne_forms /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# If test passes, reload nginx
sudo systemctl reload nginx
```

### Step 4: Verify the Fix

1. **Check nginx status:**
   ```bash
   sudo systemctl status nginx
   ```

2. **Test with a large file:**
   - Go to SNE Form page
   - Try uploading a photo between 1-2MB
   - Should succeed without 413 error

3. **Monitor nginx logs:**
   ```bash
   sudo tail -f /var/log/nginx/error.log
   ```

---

## Configuration Details

### Current File Size Limits

| Layer | Limit | Purpose |
|-------|-------|---------|
| **Client-side (JavaScript)** | 2MB | Prevents accidental large uploads |
| **Flask (MAX_CONTENT_LENGTH)** | 16MB | Application-level limit |
| **nginx (client_max_body_size)** | **20MB (after fix)** | Reverse proxy limit |

### Why 20MB for nginx?

- Flask limit: 16MB
- Add overhead for HTTP headers, form data, etc.
- 20MB provides safe buffer

---

## Additional nginx Tuning (Optional)

For better handling of large uploads, also add these to your nginx config:

```nginx
server {
    # ... existing config ...
    
    # Upload size
    client_max_body_size 20M;
    
    # Timeouts for large uploads (5 minutes)
    client_body_timeout 300s;
    client_header_timeout 300s;
    
    # Buffer sizes
    client_body_buffer_size 128k;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        
        # Proxy timeouts
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
        
        # Disable buffering for large uploads
        proxy_request_buffering off;
        
        # ... rest of proxy settings ...
    }
}
```

---

## Changes Made to Application Code

### 1. Client-Side Validation (form.html)

Added JavaScript to validate file size before upload:
- Checks file size on selection
- Shows clear error message if > 2MB
- Prevents form submission with oversized files

**Location:** `app/templates/form.html` (bottom of `<script>` section)

### 2. Flask Error Handler (__init__.py)

Added error handler for 413 errors:
- Catches payload too large errors
- Shows user-friendly error message
- Logs the error for debugging

**Location:** `app/__init__.py` (error handlers section)

---

## Troubleshooting

### Problem: Still getting 413 errors after nginx update

**Check:**
1. Did you reload nginx? `sudo systemctl reload nginx`
2. Is the setting in the correct server block (HTTP vs HTTPS)?
3. Check nginx error logs: `sudo tail -f /var/log/nginx/error.log`
4. Verify nginx config: `sudo nginx -t`

### Problem: Files larger than 2MB won't upload

**This is intentional.** To change the limit:

1. **Update client-side validation** in `app/templates/form.html`:
   ```javascript
   const MAX_FILE_SIZE = 5 * 1024 * 1024; // Change to 5MB
   ```

2. **Update the form hint** in `app/templates/form.html`:
   ```html
   <small>(Optional. Allowed: png, jpg, jpeg, gif. Max 5MB)</small>
   ```

3. **Ensure nginx limit is higher** than your new limit

### Problem: nginx won't reload

**Check syntax:**
```bash
sudo nginx -t
```

**Check if nginx is running:**
```bash
sudo systemctl status nginx
```

**Restart if needed:**
```bash
sudo systemctl restart nginx
```

---

## Testing Checklist

- [ ] nginx configuration updated with `client_max_body_size 20M`
- [ ] nginx configuration tested: `sudo nginx -t`
- [ ] nginx reloaded: `sudo systemctl reload nginx`
- [ ] Uploaded test photo < 2MB - ✅ Success
- [ ] Attempted upload > 2MB - ❌ Blocked by client-side validation
- [ ] Checked error logs for any issues

---

## Production Deployment Commands

```bash
# 1. Update nginx configuration
sudo nano /etc/nginx/sites-available/rssb_sne_forms
# Add: client_max_body_size 20M;

# 2. Test nginx configuration
sudo nginx -t

# 3. Reload nginx (zero downtime)
sudo systemctl reload nginx

# 4. Deploy updated application code
cd /path/to/rssb_sne_forms
git pull origin main  # or your deployment method

# 5. Restart application (if using systemd)
sudo systemctl restart rssb_sne_forms

# 6. Or restart Gunicorn
sudo systemctl restart gunicorn

# 7. Verify everything is working
curl -I https://your-domain.com
```

---

## Monitoring and Logs

**Watch for upload errors:**
```bash
# Flask application logs
tail -f /var/log/rssb_sne_forms/app.log

# nginx error logs
sudo tail -f /var/log/nginx/error.log

# nginx access logs
sudo tail -f /var/log/nginx/access.log
```

**Common log entries:**

- ✅ **Successful upload:** HTTP 200/302 response
- ❌ **413 before fix:** "client intended to send too large body"
- ⚠️ **Client validation:** No server request (blocked by JavaScript)

---

## Support

If issues persist after following this guide:

1. Check all three layers (client, Flask, nginx) are configured correctly
2. Review nginx error logs
3. Test with different file sizes to isolate the problem
4. Verify Gunicorn/Flask app is running and receiving requests

---

## Summary

**The 413 error is fixed by:**
1. ✅ Updated client-side validation (already done)
2. ✅ Updated Flask error handling (already done)
3. ⚠️ **YOU MUST UPDATE nginx config** → Add `client_max_body_size 20M;`

**After updating nginx and reloading, the error should be completely resolved.**
