# Movie Agent Admin Panel

## Overview
The Movie Agent Admin Panel allows you to manage and configure all movie search agents in the system. You can enable/disable individual agents, view statistics, and control which agents are used for movie searches.

## Features

### 🎛️ Agent Management
- **Toggle Individual Agents**: Enable or disable specific agents with toggle switches
- **Bulk Operations**: Enable or disable all agents at once
- **Real-time Updates**: Changes are applied immediately without server restart
- **Visual Status**: Clear visual indicators for enabled/disabled agents

### 📊 Statistics Dashboard
- **Total Agents**: View the total number of available agents
- **Enabled/Disabled Count**: See how many agents are currently active
- **Agent Details**: View descriptions and current status of each agent

### 🔧 Available Agents
1. **Enhanced DownloadHub Agent** - Searches and extracts download links from DownloadHub
2. **MoviezWap Agent** - Searches and extracts download links from MoviezWap
3. **MovieRulz Agent** - Searches and extracts download links from MovieRulz
4. **SkySetX Agent** - Searches and extracts download links from SkySetX
5. **Telegram Movie Agent** - Searches movies through Telegram channels

## How to Access

### Method 1: Direct URL
1. Start the web server: `python3 web_interface.py`
2. Open your browser to: `http://localhost:8080/admin`

### Method 2: From Main Interface
1. Start the web server: `python3 web_interface.py`
2. Go to the main page: `http://localhost:8080`
3. Click the "Admin Panel" link in the top-right corner

## How It Works

### Configuration Management
- Agent settings are stored in `agent_config.json`
- Changes are persisted automatically
- The system uses the `AgentManager` class to handle all agent operations

### Agent Initialization
- Only enabled agents are initialized and loaded into memory
- Disabled agents are completely bypassed during movie searches
- Changes take effect immediately without requiring a server restart

### Search Behavior
When you search for movies:
- Only **enabled** agents will be used for searching
- Disabled agents will be completely skipped
- This allows you to control which sources are searched

## Usage Examples

### Scenario 1: Disable Slow Agents
If certain agents are slow or unreliable:
1. Go to Admin Panel
2. Toggle off the problematic agents
3. Continue using only the fast, reliable agents

### Scenario 2: Test New Agents
When testing or debugging:
1. Disable all agents except the one you want to test
2. Run searches to isolate behavior
3. Re-enable other agents when done

### Scenario 3: Maintenance Mode
During maintenance:
1. Use "Disable All Agents" to stop all searches
2. Perform maintenance tasks
3. Use "Enable All Agents" to restore service

## Technical Details

### Files Created/Modified
- `agent_manager.py` - Core agent management logic
- `agent_config.json` - Agent configuration storage
- `templates/admin.html` - Admin panel interface
- `web_interface.py` - Added admin routes and integration

### API Endpoints
- `GET /admin` - Admin panel interface
- `GET /admin/agents` - Get agent configuration
- `POST /admin/agents/toggle` - Toggle individual agent
- `POST /admin/agents/enable-all` - Enable all agents
- `POST /admin/agents/disable-all` - Disable all agents
- `POST /admin/agents/save` - Save configuration
- `GET /admin/agents/stats` - Get agent statistics

### Configuration Format
```json
{
  "agents": {
    "agent_key": {
      "name": "Agent Display Name",
      "enabled": true/false,
      "description": "Agent description"
    }
  }
}
```

## Benefits

1. **Performance Control**: Disable slow or unreliable agents
2. **Resource Management**: Reduce memory usage by disabling unused agents
3. **Debugging**: Isolate specific agents for testing
4. **Maintenance**: Easy bulk operations for system maintenance
5. **User Experience**: Real-time configuration without server restarts

## Security Note
The admin panel should only be accessible to authorized users. In a production environment, consider adding authentication and access controls.