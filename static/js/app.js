// Movie Agent JavaScript

document.addEventListener('DOMContentLoaded', function() {
    const searchForm = document.getElementById('searchForm');
    const movieNameInput = document.getElementById('movieName');
    const searchBtn = document.getElementById('searchBtn');
    const loadingSpinner = document.getElementById('loadingSpinner');
    const resultsSection = document.getElementById('resultsSection');
    const resultsTitle = document.getElementById('resultsTitle');
    const resultsContainer = document.getElementById('resultsContainer');
    const noResultsAlert = document.getElementById('noResultsAlert');
    const errorAlert = document.getElementById('errorAlert');
    const errorMessage = document.getElementById('errorMessage');
    const videoModal = new bootstrap.Modal(document.getElementById('videoModal'));

    // Search form submission
    searchForm.addEventListener('submit', function(e) {
        e.preventDefault();
        const movieName = movieNameInput.value.trim();
        
        if (!movieName) {
            showError('Please enter a movie name');
            return;
        }

        searchMovies(movieName);
    });

    function searchMovies(movieName) {
        // Show loading state
        showLoading();
        hideResults();
        hideAlerts();

        // Make API request
        fetch('/search', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ movie_name: movieName })
        })
        .then(response => response.json())
        .then(data => {
            hideLoading();
            
            if (data.error) {
                showError(data.error);
                return;
            }

            if (data.results && data.results.length > 0) {
                displayResults(data);
            } else {
                showNoResults();
            }
        })
        .catch(error => {
            hideLoading();
            showError('An error occurred while searching. Please try again.');
            console.error('Error:', error);
        });
    }

    function displayResults(data) {
        resultsTitle.textContent = `Found ${data.total_found} results for "${data.movie_name}"`;
        resultsContainer.innerHTML = '';

        data.results.forEach((result, index) => {
            const movieCard = createMovieCard(result, index);
            resultsContainer.appendChild(movieCard);
        });

        showResults();
    }

    function createMovieCard(result, index) {
        const card = document.createElement('div');
        card.className = 'movie-card';
        
        const videoSourcesHtml = result.video_sources.map((source, sourceIndex) => `
            <div class="video-source">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <span class="quality-badge me-2">${source.quality}</span>
                        <span class="text-muted">${source.type.toUpperCase()}</span>
                        ${source.embeddable === false ? '<span class="badge bg-warning text-dark ms-1">External</span>' : '<span class="badge bg-success ms-1">Embeddable</span>'}
                    </div>
                    <div class="btn-group">
                        <button class="btn btn-play btn-sm" onclick="playVideo('${escapeHtml(source.url)}', '${escapeHtml(result.title)}', '${source.type}')">
                            <i class="fas fa-play"></i> ${source.embeddable === false ? 'Open' : 'Play'}
                        </button>
                        ${source.proxy_url ? `
                            <button class="btn btn-outline-primary btn-sm" onclick="playVideoProxy('${escapeHtml(source.proxy_url)}', '${escapeHtml(result.title)}')">
                                <i class="fas fa-shield-alt"></i> Proxy
                            </button>
                        ` : ''}
                    </div>
                </div>
                <div class="mt-2">
                    <small class="text-muted">
                        <i class="fas fa-link"></i> 
                        ${truncateUrl(source.url)}
                    </small>
                </div>
            </div>
        `).join('');

        card.innerHTML = `
            <div class="card">
                <div class="card-header">
                    <div class="d-flex justify-content-between align-items-center">
                        <h5 class="mb-0">
                            <i class="fas fa-film"></i> ${escapeHtml(result.title)}
                        </h5>
                        <div>
                            <span class="site-badge me-2">${escapeHtml(result.site)}</span>
                            <span class="match-score">${Math.round(result.match_score * 100)}% match</span>
                        </div>
                    </div>
                </div>
                <div class="card-body">
                    <div class="mb-3">
                        <strong>Available Sources (${result.video_sources.length}):</strong>
                    </div>
                    ${videoSourcesHtml}
                    <div class="mt-3">
                        <div class="btn-group" role="group">
                            <a href="${escapeHtml(result.movie_page)}" target="_blank" class="btn btn-outline-primary btn-sm">
                                <i class="fas fa-external-link-alt"></i> View Movie Page
                            </a>
                            <button class="btn btn-outline-success btn-sm" onclick="deepSearchVideo('${escapeHtml(result.movie_page)}', '${escapeHtml(result.title)}', ${index})">
                                <i class="fas fa-search-plus"></i> Deep Search
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        return card;
    }

    // Global function to play video
    window.playVideo = function(videoUrl, movieTitle, videoType = 'iframe') {
        const videoContainer = document.getElementById('videoContainer');
        const videoModalTitle = document.getElementById('videoModalTitle');
        const openInNewTab = document.getElementById('openInNewTab');

        videoModalTitle.textContent = movieTitle;
        openInNewTab.href = videoUrl;

        // Clear previous content
        videoContainer.innerHTML = '';

        if (videoType === 'video' || videoUrl.includes('.mp4') || videoUrl.includes('.m3u8')) {
            // Direct video file
            videoContainer.innerHTML = `
                <video controls autoplay style="width: 100%; height: 100%;">
                    <source src="${escapeHtml(videoUrl)}" type="video/mp4">
                    <source src="${escapeHtml(videoUrl)}" type="application/x-mpegURL">
                    Your browser does not support the video tag.
                </video>
            `;
        } else {
            // Try iframe first
            const iframe = document.createElement('iframe');
            iframe.src = videoUrl;
            iframe.style.width = '100%';
            iframe.style.height = '100%';
            iframe.style.border = 'none';
            iframe.allowFullscreen = true;
            iframe.allow = 'autoplay; encrypted-media; picture-in-picture';
            
            // Add error handling for iframe
            iframe.onerror = function() {
                console.log('Iframe failed to load, showing fallback');
                showVideoFallback(videoUrl, movieTitle);
            };
            
            // Check if iframe loads successfully
            iframe.onload = function() {
                try {
                    // Try to access iframe content to check if it loaded properly
                    if (iframe.contentDocument === null) {
                        // Iframe blocked by CORS, show fallback
                        setTimeout(() => showVideoFallback(videoUrl, movieTitle), 3000);
                    }
                } catch (e) {
                    // Cross-origin, but iframe might still work
                    console.log('Cross-origin iframe, but may still work');
                }
            };
            
            videoContainer.appendChild(iframe);
            
            // Fallback after 5 seconds if iframe doesn't work
            setTimeout(() => {
                if (iframe.contentDocument === null || iframe.contentWindow.location.href === 'about:blank') {
                    showVideoFallback(videoUrl, movieTitle);
                }
            }, 5000);
        }

        videoModal.show();
    };

    function showVideoFallback(videoUrl, movieTitle) {
        const videoContainer = document.getElementById('videoContainer');
        videoContainer.innerHTML = `
            <div class="d-flex flex-column justify-content-center align-items-center h-100 text-center p-4">
                <i class="fas fa-exclamation-triangle fa-3x text-warning mb-3"></i>
                <h5>Video Cannot Be Embedded</h5>
                <p class="text-muted mb-4">This video source doesn't allow embedding. You can watch it directly on the source website.</p>
                <div class="d-grid gap-2">
                    <a href="${escapeHtml(videoUrl)}" target="_blank" class="btn btn-primary">
                        <i class="fas fa-external-link-alt"></i> Watch on Source Website
                    </a>
                    <button class="btn btn-secondary" onclick="tryDirectVideo('${escapeHtml(videoUrl)}', '${escapeHtml(movieTitle)}')">
                        <i class="fas fa-play"></i> Try Direct Video
                    </button>
                </div>
            </div>
        `;
    }

    // Try to play video directly
    window.tryDirectVideo = function(videoUrl, movieTitle) {
        const videoContainer = document.getElementById('videoContainer');
        videoContainer.innerHTML = `
            <video controls autoplay style="width: 100%; height: 100%;" onerror="handleVideoError('${escapeHtml(videoUrl)}', '${escapeHtml(movieTitle)}')">
                <source src="${escapeHtml(videoUrl)}" type="video/mp4">
                <source src="${escapeHtml(videoUrl)}" type="application/x-mpegURL">
                <p>Your browser does not support the video tag. <a href="${escapeHtml(videoUrl)}" target="_blank">Click here to watch</a></p>
            </video>
        `;
    };

    window.handleVideoError = function(videoUrl, movieTitle) {
        const videoContainer = document.getElementById('videoContainer');
        videoContainer.innerHTML = `
            <div class="d-flex flex-column justify-content-center align-items-center h-100 text-center p-4">
                <i class="fas fa-times-circle fa-3x text-danger mb-3"></i>
                <h5>Video Playback Failed</h5>
                <p class="text-muted mb-4">Unable to play this video directly. Please try the source website.</p>
                <a href="${escapeHtml(videoUrl)}" target="_blank" class="btn btn-primary">
                    <i class="fas fa-external-link-alt"></i> Open Source Website
                </a>
            </div>
        `;
    };

    // Play video through proxy
    window.playVideoProxy = function(proxyUrl, movieTitle) {
        const videoContainer = document.getElementById('videoContainer');
        const videoModalTitle = document.getElementById('videoModalTitle');
        const openInNewTab = document.getElementById('openInNewTab');

        videoModalTitle.textContent = movieTitle + ' (Proxied)';
        openInNewTab.href = proxyUrl;

        videoContainer.innerHTML = `
            <video controls autoplay style="width: 100%; height: 100%;" onerror="handleProxyError('${escapeHtml(proxyUrl)}', '${escapeHtml(movieTitle)}')">
                <source src="${escapeHtml(proxyUrl)}" type="video/mp4">
                <p>Loading video through proxy... <a href="${escapeHtml(proxyUrl)}" target="_blank">Click here if video doesn't load</a></p>
            </video>
        `;

        videoModal.show();
    };

    window.handleProxyError = function(proxyUrl, movieTitle) {
        const videoContainer = document.getElementById('videoContainer');
        videoContainer.innerHTML = `
            <div class="d-flex flex-column justify-content-center align-items-center h-100 text-center p-4">
                <i class="fas fa-exclamation-triangle fa-3x text-warning mb-3"></i>
                <h5>Proxy Playback Failed</h5>
                <p class="text-muted mb-4">The proxy couldn't stream this video. The source may be protected or unavailable.</p>
                <a href="${escapeHtml(proxyUrl)}" target="_blank" class="btn btn-primary">
                    <i class="fas fa-external-link-alt"></i> Try Direct Link
                </a>
            </div>
        `;
    };

    // Deep search for video sources
    window.deepSearchVideo = function(moviePageUrl, movieTitle, resultIndex) {
        const button = event.target;
        const originalText = button.innerHTML;
        
        button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Searching...';
        button.disabled = true;

        fetch(`/extract_video_direct?url=${encodeURIComponent(moviePageUrl)}`)
            .then(response => response.json())
            .then(data => {
                if (data.video_sources && data.video_sources.length > 0) {
                    // Update the result with new video sources
                    updateVideoSources(resultIndex, data.video_sources);
                    showSuccess('Found additional video sources!');
                } else {
                    showError('No additional video sources found');
                }
            })
            .catch(error => {
                console.error('Deep search error:', error);
                showError('Deep search failed. Please try again.');
            })
            .finally(() => {
                button.innerHTML = originalText;
                button.disabled = false;
            });
    };

    function updateVideoSources(resultIndex, newVideoSources) {
        // Find the movie card and update its video sources
        const movieCards = document.querySelectorAll('.movie-card');
        if (movieCards[resultIndex]) {
            const card = movieCards[resultIndex];
            const sourcesContainer = card.querySelector('.card-body');
            
            // Create new video sources HTML
            const newSourcesHtml = newVideoSources.map(source => `
                <div class="video-source">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <span class="quality-badge me-2">${source.quality}</span>
                            <span class="text-muted">${source.type.toUpperCase()}</span>
                            <span class="badge bg-info ms-1">Deep Search</span>
                        </div>
                        <div class="btn-group">
                            <button class="btn btn-play btn-sm" onclick="playVideo('${escapeHtml(source.url)}', 'Deep Search Video', '${source.type}')">
                                <i class="fas fa-play"></i> Play
                            </button>
                            ${source.proxy_url ? `
                                <button class="btn btn-outline-primary btn-sm" onclick="playVideoProxy('${escapeHtml(source.proxy_url)}', 'Deep Search Video')">
                                    <i class="fas fa-shield-alt"></i> Proxy
                                </button>
                            ` : ''}
                        </div>
                    </div>
                    <div class="mt-2">
                        <small class="text-muted">
                            <i class="fas fa-link"></i> 
                            ${truncateUrl(source.url)}
                        </small>
                    </div>
                </div>
            `).join('');
            
            // Add new sources before the movie page link
            const moviePageDiv = card.querySelector('.mt-3');
            moviePageDiv.insertAdjacentHTML('beforebegin', `
                <div class="mb-3">
                    <strong>Deep Search Results (${newVideoSources.length}):</strong>
                </div>
                ${newSourcesHtml}
            `);
        }
    }

    function showSuccess(message) {
        // Create a temporary success alert
        const alert = document.createElement('div');
        alert.className = 'alert alert-success alert-dismissible fade show position-fixed';
        alert.style.top = '20px';
        alert.style.right = '20px';
        alert.style.zIndex = '9999';
        alert.innerHTML = `
            <i class="fas fa-check-circle"></i> ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        document.body.appendChild(alert);
        
        // Auto remove after 3 seconds
        setTimeout(() => {
            if (alert.parentNode) {
                alert.parentNode.removeChild(alert);
            }
        }, 3000);
    }

    // Utility functions
    function showLoading() {
        loadingSpinner.classList.remove('d-none');
        searchBtn.disabled = true;
        searchBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Searching...';
    }

    function hideLoading() {
        loadingSpinner.classList.add('d-none');
        searchBtn.disabled = false;
        searchBtn.innerHTML = '<i class="fas fa-search"></i> Search Movies';
    }

    function showResults() {
        resultsSection.classList.remove('d-none');
    }

    function hideResults() {
        resultsSection.classList.add('d-none');
    }

    function showNoResults() {
        noResultsAlert.classList.remove('d-none');
    }

    function showError(message) {
        errorMessage.textContent = message;
        errorAlert.classList.remove('d-none');
    }

    function hideAlerts() {
        noResultsAlert.classList.add('d-none');
        errorAlert.classList.add('d-none');
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function truncateUrl(url, maxLength = 50) {
        if (url.length <= maxLength) return url;
        return url.substring(0, maxLength) + '...';
    }

    // Clear video when modal is closed
    document.getElementById('videoModal').addEventListener('hidden.bs.modal', function() {
        document.getElementById('videoContainer').innerHTML = '';
    });

    // Sample searches for demonstration
    const sampleSearches = ['My Baby', 'Inception', 'Avatar', 'Avengers', 'Spider-Man'];
    let currentSample = 0;

    // Add placeholder rotation
    setInterval(() => {
        movieNameInput.placeholder = `Enter movie name (e.g., ${sampleSearches[currentSample]})`;
        currentSample = (currentSample + 1) % sampleSearches.length;
    }, 3000);
});