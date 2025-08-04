/**
 * Enhanced Chat Interface JavaScript
 * Provides advanced chat functionality with improved UX
 */

class EnhancedChatInterface {
    constructor() {
        this.conversationHistory = [];
        this.isWaitingForResponse = false;
        this.messageQueue = [];
        this.typingSpeed = 50; // ms per character
        this.maxRetries = 3;
        this.retryDelay = 1000;
        
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.setupKeyboardShortcuts();
        this.setupAutoSave();
        this.setupNotifications();
        this.setupVisualEnhancements();
        this.loadChatHistory();
        
        // Focus input on load
        setTimeout(() => {
            document.getElementById('chatInput')?.focus();
        }, 100);
    }

    setupVisualEnhancements() {
        // Add floating particles effect
        this.createFloatingParticles();
        
        // Setup smooth scrolling
        this.setupSmoothScrolling();
        
        // Add message entrance animations
        this.setupMessageAnimations();
        
        // Setup theme transitions
        this.setupThemeTransitions();
    }

    createFloatingParticles() {
        const particleCount = 20;
        const container = document.body;
        
        for (let i = 0; i < particleCount; i++) {
            const particle = document.createElement('div');
            particle.className = 'floating-particle';
            particle.style.cssText = `
                position: fixed;
                width: ${Math.random() * 4 + 2}px;
                height: ${Math.random() * 4 + 2}px;
                background: rgba(255, 255, 255, ${Math.random() * 0.3 + 0.1});
                border-radius: 50%;
                left: ${Math.random() * 100}%;
                top: ${Math.random() * 100}%;
                pointer-events: none;
                z-index: 0;
                animation: float ${Math.random() * 3 + 4}s ease-in-out infinite;
                animation-delay: ${Math.random() * 2}s;
            `;
            container.appendChild(particle);
        }
    }

    setupSmoothScrolling() {
        const messagesContainer = document.getElementById('chatMessages');
        if (messagesContainer) {
            messagesContainer.style.scrollBehavior = 'smooth';
        }
    }

    setupMessageAnimations() {
        // Enhanced message entrance animations
        const style = document.createElement('style');
        style.textContent = `
            .message {
                animation: messageSlideIn 0.6s cubic-bezier(0.4, 0, 0.2, 1);
                animation-fill-mode: both;
            }
            
            @keyframes messageSlideIn {
                from {
                    opacity: 0;
                    transform: translateY(30px) scale(0.95);
                }
                to {
                    opacity: 1;
                    transform: translateY(0) scale(1);
                }
            }
            
            .message.user {
                animation: messageSlideInRight 0.6s cubic-bezier(0.4, 0, 0.2, 1);
            }
            
            @keyframes messageSlideInRight {
                from {
                    opacity: 0;
                    transform: translateX(30px) scale(0.95);
                }
                to {
                    opacity: 1;
                    transform: translateX(0) scale(1);
                }
            }
        `;
        document.head.appendChild(style);
    }

    setupThemeTransitions() {
        // Add smooth transitions for theme changes
        document.documentElement.style.transition = 'all 0.3s ease';
    }
    setupEventListeners() {
        const chatInput = document.getElementById('chatInput');
        const sendBtn = document.getElementById('sendBtn');

        if (chatInput) {
            chatInput.addEventListener('input', this.handleInputChange.bind(this));
            chatInput.addEventListener('keydown', this.handleKeyDown.bind(this));
            chatInput.addEventListener('paste', this.handlePaste.bind(this));
            chatInput.addEventListener('focus', this.handleInputFocus.bind(this));
            chatInput.addEventListener('blur', this.handleInputBlur.bind(this));
        }

        if (sendBtn) {
            sendBtn.addEventListener('click', this.sendMessage.bind(this));
        }

        // Setup intersection observer for message visibility
        this.setupMessageObserver();
        
        // Setup sidebar toggle for mobile
        this.setupSidebarToggle();
    }

    handleInputFocus(e) {
        const inputWrapper = e.target.closest('.input-wrapper');
        if (inputWrapper) {
            inputWrapper.style.transform = 'translateY(-2px)';
            inputWrapper.style.boxShadow = '0 8px 25px rgba(102, 126, 234, 0.2)';
        }
    }

    handleInputBlur(e) {
        const inputWrapper = e.target.closest('.input-wrapper');
        if (inputWrapper) {
            inputWrapper.style.transform = 'translateY(0)';
            inputWrapper.style.boxShadow = 'none';
        }
    }
    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Ctrl/Cmd + Enter to send message
            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                e.preventDefault();
                this.sendMessage();
            }
            
            // Escape to clear input
            if (e.key === 'Escape') {
                this.clearInput();
            }
            
            // Ctrl/Cmd + K to focus search
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                document.getElementById('chatInput')?.focus();
            }
            
            // Ctrl/Cmd + / to toggle sidebar
            if ((e.ctrlKey || e.metaKey) && e.key === '/') {
                e.preventDefault();
                this.toggleSidebar();
            }
        });
    }

    setupAutoSave() {
        // Auto-save conversation every 30 seconds
        setInterval(() => {
            this.saveChatHistory();
        }, 30000);
        
        // Save on page unload
        window.addEventListener('beforeunload', () => {
            this.saveChatHistory();
        });
    }

    setupNotifications() {
        // Request notification permission
        if ('Notification' in window && Notification.permission === 'default') {
            Notification.requestPermission();
        }
    }

    setupMessageObserver() {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('visible');
                }
            });
        }, { threshold: 0.1 });

        // Observe existing messages
        document.querySelectorAll('.message').forEach(msg => {
            observer.observe(msg);
        });

        this.messageObserver = observer;
    }

    setupSidebarToggle() {
        const toggleBtn = document.createElement('button');
        toggleBtn.className = 'sidebar-toggle';
        toggleBtn.innerHTML = '<i class="fas fa-bars"></i>';
        toggleBtn.style.display = 'none';
        
        toggleBtn.addEventListener('click', () => {
            const sidebar = document.querySelector('.sidebar');
            sidebar?.classList.toggle('open');
        });

        document.body.appendChild(toggleBtn);

        // Show toggle on mobile
        const mediaQuery = window.matchMedia('(max-width: 768px)');
        const handleMediaChange = (e) => {
            toggleBtn.style.display = e.matches ? 'flex' : 'none';
        };
        
        mediaQuery.addListener(handleMediaChange);
        handleMediaChange(mediaQuery);
    }

    handleInputChange(e) {
        const input = e.target;
        this.autoResize(input);
        
        // Show typing indicator to other users (if multi-user)
        this.debounce(() => {
            this.handleTyping(input.value);
        }, 300)();
    }

    handleKeyDown(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            this.sendMessage();
        }
        
        // Handle arrow keys for message history
        if (e.key === 'ArrowUp' && e.target.value === '') {
            e.preventDefault();
            this.showPreviousMessage();
        }
    }

    handlePaste(e) {
        // Handle file paste
        const items = e.clipboardData?.items;
        if (items) {
            for (let item of items) {
                if (item.type.indexOf('image') !== -1) {
                    e.preventDefault();
                    const file = item.getAsFile();
                    this.handleImageUpload(file);
                }
            }
        }
    }

    handleTyping(value) {
        // Implement typing indicator logic
        if (value.length > 0) {
            this.showUserTyping();
        } else {
            this.hideUserTyping();
        }
    }

    autoResize(textarea) {
        textarea.style.height = 'auto';
        const maxHeight = 120;
        const newHeight = Math.min(textarea.scrollHeight, maxHeight);
        textarea.style.height = newHeight + 'px';
        
        // Scroll to bottom if needed
        if (textarea.scrollHeight > maxHeight) {
            textarea.scrollTop = textarea.scrollHeight;
        }
    }

    async sendMessage(messageText = null) {
        const input = document.getElementById('chatInput');
        const message = messageText || input?.value.trim();
        
        if (!message || this.isWaitingForResponse) return;
        
        // Clear input and hide welcome screen
        if (input) {
            input.value = '';
            input.style.height = 'auto';
        }
        this.hideWelcomeScreen();
        
        // Add user message with animation
        await this.addMessage(message, 'user');
        
        // Show typing indicator
        this.showTypingIndicator();
        this.isWaitingForResponse = true;
        
        try {
            const response = await this.fetchWithRetry('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: message,
                    conversation_history: this.conversationHistory
                })
            });

            const data = await response.json();
            
            if (data.success) {
                // Type out AI response with animation
                await this.typeMessage(data.response, 'assistant', data.movie_results);
                
                // Update conversation history
                this.conversationHistory = data.conversation_history || [];
                
                // Show suggestions if any
                if (data.suggestions && data.suggestions.length > 0) {
                    this.showSuggestions(data.suggestions);
                }
                
                // Show notification if page is not visible
                this.showNotificationIfHidden('New AI response received');
                
            } else {
                await this.typeMessage('Sorry, I encountered an error. Please try again.', 'assistant');
            }
            
        } catch (error) {
            console.error('Error:', error);
            await this.typeMessage('Sorry, I encountered a connection error. Please try again.', 'assistant');
            this.showErrorMessage('Connection failed. Please check your internet connection.');
        } finally {
            this.hideTypingIndicator();
            this.isWaitingForResponse = false;
            this.saveChatHistory();
        }
    }

    async fetchWithRetry(url, options, retries = this.maxRetries) {
        try {
            const response = await fetch(url, options);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return response;
        } catch (error) {
            if (retries > 0) {
                await this.delay(this.retryDelay);
                return this.fetchWithRetry(url, options, retries - 1);
            }
            throw error;
        }
    }

    async addMessage(content, sender, movieResults = null, animate = true) {
        const messagesContainer = document.getElementById('chatMessages');
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}`;
        
        if (animate) {
            messageDiv.style.opacity = '0';
            messageDiv.style.transform = 'translateY(20px)';
        }
        
        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        avatar.innerHTML = this.getAvatarContent(sender);
        
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        
        let messageHTML = `<div class="message-text">${this.formatMessage(content)}</div>`;
        
        // Add timestamp
        const now = new Date();
        const timeString = now.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
        messageHTML += `<div class="message-time">${timeString}</div>`;
        
        // Add movie results if available
        if (movieResults && movieResults.length > 0) {
            messageHTML += this.createMovieResultsHTML(movieResults);
        }
        
        // Add message reactions
        if (sender === 'assistant') {
            messageHTML += this.createMessageReactions();
        }
        
        messageContent.innerHTML = messageHTML;
        
        if (sender === 'user') {
            messageDiv.appendChild(messageContent);
            messageDiv.appendChild(avatar);
        } else {
            messageDiv.appendChild(avatar);
            messageDiv.appendChild(messageContent);
        }
        
        messagesContainer.appendChild(messageDiv);
        
        // Animate message appearance
        if (animate) {
            await this.delay(50);
            messageDiv.style.transition = 'all 0.3s ease-out';
            messageDiv.style.opacity = '1';
            messageDiv.style.transform = 'translateY(0)';
        }
        
        this.scrollToBottom();
        
        // Observe new message
        if (this.messageObserver) {
            this.messageObserver.observe(messageDiv);
        }
        
        return messageDiv;
    }

    async typeMessage(content, sender, movieResults = null) {
        const messageDiv = await this.addMessage('', sender, movieResults, true);
        const textElement = messageDiv.querySelector('.message-text');
        
        if (!textElement) return;
        
        const formattedContent = this.formatMessage(content);
        
        // Type out the message character by character
        for (let i = 0; i <= formattedContent.length; i++) {
            textElement.innerHTML = formattedContent.substring(0, i);
            this.scrollToBottom();
            await this.delay(this.typingSpeed);
        }
    }

    getAvatarContent(sender) {
        if (sender === 'user') {
            return '<i class="fas fa-user"></i>';
        } else {
            return '<i class="fas fa-robot"></i>';
        }
    }

    formatMessage(text) {
        return text
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`(.*?)`/g, '<code>$1</code>')
            .replace(/\n/g, '<br>')
            .replace(/(https?:\/\/[^\s]+)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>');
    }

    createMovieResultsHTML(movies) {
        let html = `
            <div class="movie-results">
                <h4><i class="fas fa-film"></i> Found ${movies.length} movies:</h4>
        `;
        
        movies.slice(0, 5).forEach((movie, index) => {
            html += `
                <div class="movie-item" style="animation-delay: ${index * 0.1}s">
                    <div class="movie-title">${this.escapeHtml(movie.title)}</div>
                    <div class="movie-details">
                        <span class="movie-badge">${movie.year || 'Unknown'}</span>
                        <span class="movie-badge">${movie.quality || 'Unknown'}</span>
                        <span class="movie-badge">${movie.source}</span>
                    </div>
                    <div class="movie-actions">
                        <button class="action-btn extract-btn" onclick="chatInterface.extractMovieLinks('${this.escapeHtml(movie.title)}', '${this.escapeHtml(movie.url)}', '${this.escapeHtml(movie.source)}')">
                            <i class="fas fa-download"></i> Extract Links
                        </button>
                        <button class="action-btn search-btn" onclick="chatInterface.searchMovie('${this.escapeHtml(movie.title)}')">
                            <i class="fas fa-search"></i> Search More
                        </button>
                    </div>
                </div>
            `;
        });
        
        html += '</div>';
        return html;
    }

    createMessageReactions() {
        return `
            <div class="message-reactions">
                <button class="reaction" onclick="chatInterface.addReaction(this, '👍')" title="Helpful">👍</button>
                <button class="reaction" onclick="chatInterface.addReaction(this, '❤️')" title="Love it">❤️</button>
                <button class="reaction" onclick="chatInterface.addReaction(this, '😄')" title="Funny">😄</button>
                <button class="reaction" onclick="chatInterface.addReaction(this, '🤔')" title="Thinking">🤔</button>
            </div>
        `;
    }

    addReaction(button, emoji) {
        button.classList.add('active');
        button.innerHTML = emoji + ' 1';
        
        // Animate reaction
        button.style.transform = 'scale(1.2)';
        setTimeout(() => {
            button.style.transform = 'scale(1)';
        }, 200);
    }

    showTypingIndicator() {
        const indicator = document.getElementById('typingIndicator');
        if (indicator) {
            indicator.style.display = 'flex';
            this.scrollToBottom();
        }
    }

    hideTypingIndicator() {
        const indicator = document.getElementById('typingIndicator');
        if (indicator) {
            indicator.style.display = 'none';
        }
    }

    hideWelcomeScreen() {
        const welcomeScreen = document.getElementById('welcomeScreen');
        if (welcomeScreen) {
            welcomeScreen.style.opacity = '0';
            welcomeScreen.style.transform = 'translateY(-20px)';
            setTimeout(() => {
                welcomeScreen.style.display = 'none';
            }, 300);
        }
    }

    showSuggestions(suggestions) {
        const suggestionsContainer = document.getElementById('suggestions');
        if (!suggestionsContainer) return;
        
        suggestionsContainer.innerHTML = '';
        
        suggestions.forEach((suggestion, index) => {
            const chip = document.createElement('div');
            chip.className = 'suggestion-chip';
            chip.textContent = suggestion;
            chip.style.animationDelay = `${index * 0.1}s`;
            chip.onclick = () => this.sendMessage(suggestion);
            suggestionsContainer.appendChild(chip);
        });
        
        suggestionsContainer.style.display = 'flex';
        
        // Auto-hide suggestions after 10 seconds
        setTimeout(() => {
            suggestionsContainer.style.display = 'none';
        }, 10000);
    }

    scrollToBottom() {
        const messagesContainer = document.getElementById('chatMessages');
        if (messagesContainer) {
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }
    }

    clearInput() {
        const input = document.getElementById('chatInput');
        if (input) {
            input.value = '';
            input.style.height = 'auto';
            input.focus();
        }
    }

    showPreviousMessage() {
        // Implement message history navigation
        if (this.conversationHistory.length > 0) {
            const lastUserMessage = this.conversationHistory
                .filter(msg => msg.role === 'user')
                .pop();
            
            if (lastUserMessage) {
                const input = document.getElementById('chatInput');
                if (input) {
                    input.value = lastUserMessage.content;
                    this.autoResize(input);
                }
            }
        }
    }

    extractMovieLinks(title, url, source) {
        this.showSuccessMessage(`Extracting links for "${title}"...`);
        window.location.href = `/extract?url=${encodeURIComponent(url)}&source=${encodeURIComponent(source)}&title=${encodeURIComponent(title)}`;
    }

    searchMovie(title) {
        this.showSuccessMessage(`Searching for more "${title}" results...`);
        window.location.href = `/?search=${encodeURIComponent(title)}`;
    }

    showErrorMessage(message) {
        this.showToast(message, 'error');
    }

    showSuccessMessage(message) {
        this.showToast(message, 'success');
    }

    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.innerHTML = `
            <i class="fas fa-${type === 'error' ? 'exclamation-triangle' : type === 'success' ? 'check-circle' : 'info-circle'}"></i>
            <span>${message}</span>
            <button onclick="this.parentElement.remove()"><i class="fas fa-times"></i></button>
        `;
        
        toast.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: ${type === 'error' ? '#dc3545' : type === 'success' ? '#28a745' : '#17a2b8'};
            color: white;
            padding: 15px 20px;
            border-radius: 10px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.3);
            z-index: 10000;
            max-width: 300px;
            display: flex;
            align-items: center;
            gap: 10px;
            animation: slideInRight 0.3s ease-out;
        `;
        
        document.body.appendChild(toast);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            toast.style.animation = 'slideOutRight 0.3s ease-out';
            setTimeout(() => toast.remove(), 300);
        }, 5000);
    }

    showNotificationIfHidden(message) {
        if (document.hidden && 'Notification' in window && Notification.permission === 'granted') {
            new Notification('Movie Agent AI', {
                body: message,
                icon: '/static/favicon.ico',
                badge: '/static/favicon.ico'
            });
        }
    }

    saveChatHistory() {
        try {
            localStorage.setItem('chatHistory', JSON.stringify(this.conversationHistory));
            localStorage.setItem('chatTimestamp', Date.now().toString());
        } catch (error) {
            console.warn('Failed to save chat history:', error);
        }
    }

    loadChatHistory() {
        try {
            const saved = localStorage.getItem('chatHistory');
            const timestamp = localStorage.getItem('chatTimestamp');
            
            // Only load if less than 24 hours old
            if (saved && timestamp && (Date.now() - parseInt(timestamp)) < 24 * 60 * 60 * 1000) {
                this.conversationHistory = JSON.parse(saved);
            }
        } catch (error) {
            console.warn('Failed to load chat history:', error);
        }
    }

    // Utility functions
    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Quick message senders
    sendQuickMessage(message) {
        this.sendMessage(message);
    }

    // Voice input (if supported)
    startVoiceInput() {
        if ('webkitSpeechRecognition' in window) {
            const recognition = new webkitSpeechRecognition();
            recognition.continuous = false;
            recognition.interimResults = false;
            recognition.lang = 'en-US';

            recognition.onstart = () => {
                this.showToast('Listening...', 'info');
            };

            recognition.onresult = (event) => {
                const transcript = event.results[0][0].transcript;
                const input = document.getElementById('chatInput');
                if (input) {
                    input.value = transcript;
                    this.autoResize(input);
                }
            };

            recognition.onerror = (event) => {
                this.showErrorMessage('Voice recognition error: ' + event.error);
            };

            recognition.start();
        } else {
            this.showErrorMessage('Voice recognition not supported in this browser');
        }
    }
}

// Initialize chat interface when DOM is loaded
let chatInterface;
document.addEventListener('DOMContentLoaded', function() {
    chatInterface = new EnhancedChatInterface();
    
    // Add voice input button if supported
    if ('webkitSpeechRecognition' in window) {
        const voiceBtn = document.createElement('button');
        voiceBtn.className = 'voice-btn';
        voiceBtn.innerHTML = '<i class="fas fa-microphone"></i>';
        voiceBtn.onclick = () => chatInterface.startVoiceInput();
        voiceBtn.style.cssText = `
            position: absolute;
            right: 60px;
            top: 50%;
            transform: translateY(-50%);
            background: none;
            border: none;
            color: #667eea;
            font-size: 1.1rem;
            cursor: pointer;
            padding: 5px;
            border-radius: 50%;
            transition: all 0.3s ease;
        `;
        
        const inputWrapper = document.querySelector('.input-wrapper');
        if (inputWrapper) {
            inputWrapper.style.position = 'relative';
            inputWrapper.appendChild(voiceBtn);
        }
    }
});

// Global functions for backward compatibility
function sendQuickMessage(message) {
    if (chatInterface) {
        chatInterface.sendQuickMessage(message);
    }
}

function extractMovieLinks(title, url, source) {
    if (chatInterface) {
        chatInterface.extractMovieLinks(title, url, source);
    }
}

function searchMovie(title) {
    if (chatInterface) {
        chatInterface.searchMovie(title);
    }
}

// Add CSS animations
const style = document.createElement('style');
style.textContent = `
    @keyframes slideInRight {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    
    @keyframes slideOutRight {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
    }
    
    .toast {
        animation: slideInRight 0.3s ease-out;
    }
    
    .voice-btn:hover {
        background: rgba(102, 126, 234, 0.1) !important;
        transform: translateY(-50%) scale(1.1) !important;
    }
`;
document.head.appendChild(style);