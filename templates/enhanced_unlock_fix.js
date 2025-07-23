// Enhanced unlock function that creates collapsible section
function displayUnlockedLinks(originalIndex, unlockedLinks, originalLinkDiv) {
    // Don't remove the original link, instead update it and add collapsible section
    const unlockBtn = originalLinkDiv.querySelector('.unlock-btn');
    const downloadBtn = originalLinkDiv.querySelector('.download-btn');
    
    // Update the unlock button to show success
    if (unlockBtn) {
        unlockBtn.textContent = 'Unlocked!';
        unlockBtn.style.background = 'linear-gradient(45deg, #4CAF50, #45a049)';
        unlockBtn.disabled = true;
    }
    
    // Update the download button
    if (downloadBtn) {
        downloadBtn.textContent = 'View Links Below';
        downloadBtn.style.background = 'linear-gradient(45deg, #4CAF50, #45a049)';
        downloadBtn.onclick = function(e) {
            e.preventDefault();
            const container = originalLinkDiv.querySelector('.unlocked-links-container');
            if (container) {
                container.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }
        };
    }
    
    // Create collapsible container for unlocked links
    let unlockedContainer = originalLinkDiv.querySelector('.unlocked-links-container');
    if (!unlockedContainer) {
        unlockedContainer = document.createElement('div');
        unlockedContainer.className = 'unlocked-links-container';
        unlockedContainer.style.cssText = `
            margin-top: 15px;
            padding: 0;
            background: rgba(76, 175, 80, 0.1);
            border-radius: 12px;
            border: 1px solid rgba(76, 175, 80, 0.3);
            overflow: hidden;
            max-height: 0;
            transition: all 0.4s ease;
            opacity: 0;
        `;
        originalLinkDiv.appendChild(unlockedContainer);
    }
    
    // Create header
    const headerHtml = `
        <div style="display: flex; align-items: center; gap: 10px; font-weight: 600; color: #4CAF50; margin-bottom: 12px; font-size: 0.95rem;">
            <span style="background: #4CAF50; color: white; width: 24px; height: 20px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: bold;">OK</span>
            Unlocked Download Links (${unlockedLinks.length} found)
        </div>
    `;
    
    // Create unlocked links HTML
    let linksHtml = headerHtml;
    unlockedLinks.forEach((link, linkIndex) => {
        linksHtml += `
            <div style="background: rgba(255, 255, 255, 0.08); border-radius: 8px; padding: 12px; margin-bottom: 10px; border-left: 3px solid #4CAF50; transition: all 0.3s ease;" onmouseover="this.style.background='rgba(255, 255, 255, 0.12)'; this.style.transform='translateX(5px)';" onmouseout="this.style.background='rgba(255, 255, 255, 0.08)'; this.style.transform='translateX(0)';">
                <div style="display: flex; justify-content: space-between; align-items: center; gap: 15px;">
                    <div style="flex: 1;">
                        <div style="font-weight: 600; color: #fff; margin-bottom: 4px; font-size: 0.9rem;">
                            ${link.text || link.service_type || 'Download Link'}
                        </div>
                        <div style="font-size: 0.8rem; opacity: 0.8; color: rgba(255, 255, 255, 0.7);">
                            Host: ${link.host || 'Unknown'} | Quality: ${link.quality || 'Unknown'} | Size: ${link.file_size || 'Unknown'}
                        </div>
                    </div>
                    <a href="${link.url}" target="_blank" style="background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%); color: white; padding: 8px 16px; border: none; border-radius: 20px; font-size: 0.85rem; font-weight: 600; text-decoration: none; display: inline-flex; align-items: center; gap: 6px; box-shadow: 0 2px 8px rgba(76, 175, 80, 0.3); transition: all 0.3s ease;" onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 4px 12px rgba(76, 175, 80, 0.4)';" onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 2px 8px rgba(76, 175, 80, 0.3)';">
                        Download
                    </a>
                </div>
            </div>
        `;
    });
    
    unlockedContainer.innerHTML = linksHtml;
    
    // Show the container with animation
    setTimeout(() => {
        unlockedContainer.style.maxHeight = '500px';
        unlockedContainer.style.opacity = '1';
        unlockedContainer.style.padding = '15px';
        
        // Scroll to the unlocked links
        setTimeout(() => {
            unlockedContainer.scrollIntoView({ 
                behavior: 'smooth', 
                block: 'nearest' 
            });
        }, 200);
    }, 100);
}