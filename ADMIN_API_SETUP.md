# Admin Panel API Key Management Setup

## Overview
This setup allows you to manage Together API keys directly from the admin panel instead of using environment variables.

## Files Added/Modified

### 1. `config_manager.py` - Configuration Management
- Handles reading/writing API keys to `llm_config.json`
- Provides API key validation and testing
- Fallback to environment variables if needed

### 2. `admin_routes.py` - Admin API Endpoints
- `/admin/api/config` (GET/POST) - Get/Update API configuration
- `/admin/api/test` (POST) - Test API connection
- `/admin/chat/config` (GET) - Get chat configuration

### 3. `llm_chat_agent.py` - Updated LLM Agent
- Now reads API key from config files first
- Falls back to environment variables
- Integrates with config manager

## Integration with Web Interface

### Add to your `web_interface.py`:

```python
from admin_routes import register_admin_routes

# Register admin routes
register_admin_routes(app)
```

### Add JavaScript to `admin.html`:

```javascript
// Load API configuration on page load
async function loadApiConfig() {
    try {
        const response = await fetch('/admin/api/config');
        const data = await response.json();
        
        if (data.success) {
            const config = data.config;
            document.getElementById('together-api-key').value = config.api_key || '';
            document.getElementById('together-model').value = config.model || 'mistralai/Mixtral-8x7B-Instruct-v0.1';
            document.getElementById('together-max-tokens').value = config.max_tokens || 500;
            document.getElementById('together-temperature').value = config.temperature || 0.7;
            document.getElementById('together-enabled').checked = config.enabled || false;
            
            updateApiStatus(config.enabled);
        }
    } catch (error) {
        console.error('Error loading API config:', error);
    }
}

// Save API configuration
async function saveTogetherConfig() {
    try {
        const config = {
            api_key: document.getElementById('together-api-key').value,
            model: document.getElementById('together-model').value,
            max_tokens: parseInt(document.getElementById('together-max-tokens').value),
            temperature: parseFloat(document.getElementById('together-temperature').value),
            enabled: document.getElementById('together-enabled').checked
        };
        
        const response = await fetch('/admin/api/config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(config)
        });
        
        const result = await response.json();
        
        if (result.success) {
            showConfigStatus('Configuration saved successfully!', 'success');
            updateApiStatus(config.enabled);
        } else {
            showConfigStatus('Error: ' + result.error, 'error');
        }
    } catch (error) {
        showConfigStatus('Error saving configuration: ' + error.message, 'error');
    }
}

// Test API connection
async function testTogetherAPI() {
    try {
        const apiKey = document.getElementById('together-api-key').value;
        
        if (!apiKey) {
            showConfigStatus('Please enter an API key first', 'error');
            return;
        }
        
        showConfigStatus('Testing API connection...', 'info');
        
        const response = await fetch('/admin/api/test', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ api_key: apiKey })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showConfigStatus('API test successful! ' + result.message, 'success');
        } else {
            showConfigStatus('API test failed: ' + result.message, 'error');
        }
    } catch (error) {
        showConfigStatus('Error testing API: ' + error.message, 'error');
    }
}

// Toggle API key visibility
function toggleApiKeyVisibility(inputId) {
    const input = document.getElementById(inputId);
    const button = input.nextElementSibling;
    
    if (input.type === 'password') {
        input.type = 'text';
        button.textContent = 'Hide';
    } else {
        input.type = 'password';
        button.textContent = 'Show';
    }
}

// Update API status badge
function updateApiStatus(enabled) {
    const statusBadge = document.getElementById('together-status');
    if (enabled) {
        statusBadge.textContent = 'Enabled';
        statusBadge.className = 'status-badge status-enabled';
    } else {
        statusBadge.textContent = 'Disabled';
        statusBadge.className = 'status-badge status-disabled';
    }
}

// Show configuration status
function showConfigStatus(message, type) {
    const statusDiv = document.getElementById('together-test-result');
    statusDiv.textContent = message;
    statusDiv.className = `config-status ${type}`;
    statusDiv.style.display = 'block';
    
    setTimeout(() => {
        statusDiv.style.display = 'none';
    }, 5000);
}

// Load config on page load
document.addEventListener('DOMContentLoaded', loadApiConfig);
```

## Usage

### 1. **Access Admin Panel**
- Go to `/admin` in your web interface
- You'll see the new "API Configuration" section

### 2. **Configure Together API**
- Enter your Together API key
- Select model (Mixtral-8x7B-Instruct recommended)
- Adjust max tokens (100-2000)
- Set temperature (0.0-1.0)
- Enable/disable the API

### 3. **Test Configuration**
- Click "Test API" to verify connection
- Click "Save Configuration" to persist settings

### 4. **Use in Chat**
- The LLM chat agent will automatically use the configured API key
- If API is disabled, it falls back to basic functionality

## Configuration Files

### `llm_config.json` Structure:
```json
{
  "together_api": {
    "enabled": true,
    "api_key": "your_api_key_here",
    "model": "mistralai/Mixtral-8x7B-Instruct-v0.1",
    "max_tokens": 500,
    "temperature": 0.7,
    "last_updated": "2025-08-06 13:40:00"
  },
  "fallback_responses": {
    "no_api_key": "AI chat unavailable...",
    "error_response": "Sorry, error occurred...",
    "welcome_message": "Hi! I'm your AI assistant..."
  }
}
```

## Benefits

✅ **No Environment Variables**: Manage API keys through web interface  
✅ **Secure Storage**: Keys stored in config files, not exposed in UI  
✅ **Easy Testing**: Built-in API connection testing  
✅ **Live Configuration**: Changes take effect immediately  
✅ **Fallback Support**: Works without API key for basic functionality  
✅ **Admin Control**: Centralized configuration management  

## Security Notes

- API keys are stored in `llm_config.json` (ensure proper file permissions)
- Keys are hidden in the admin UI (shown as `***HIDDEN***`)
- Consider adding authentication to admin panel for production use
- Regular backup of configuration files recommended

This setup provides a complete admin interface for managing API keys without requiring server restarts or environment variable changes!