// Add this to a new file: static/js/cookie-consent.js

document.addEventListener('DOMContentLoaded', function() {
    // Check if user has already consented to cookies
    if (!localStorage.getItem('cookieConsent')) {
        showCookieBanner();
    }
    
    // Set up event listeners for the consent buttons
    document.addEventListener('click', function(event) {
        if (event.target.id === 'acceptAllCookies') {
            acceptAllCookies();
        } else if (event.target.id === 'acceptEssentialCookies') {
            acceptEssentialCookies();
        } else if (event.target.id === 'cookieSettings') {
            showCookieSettings();
        } else if (event.target.id === 'saveCookieSettings') {
            saveCookieSettings();
        }
    });
});

function showCookieBanner() {
    const banner = document.createElement('div');
    banner.id = 'cookieConsentBanner';
    banner.className = 'cookie-consent-banner';
    banner.innerHTML = `
        <div class="cookie-content">
            <div class="cookie-text">
                <h3>We Use Cookies</h3>
                <p>We use cookies to enhance your browsing experience, analyze site traffic, and improve site functionality. 
                   To learn more, read our <a href="/cookies/" class="cookie-link">Cookie Policy</a>.</p>
            </div>
            <div class="cookie-buttons">
                <button id="acceptAllCookies" class="btn btn-primary cookie-btn">Accept All</button>
                <button id="acceptEssentialCookies" class="btn btn-outline-secondary cookie-btn">Essential Only</button>
                <button id="cookieSettings" class="btn btn-link cookie-link-btn">Cookie Settings</button>
            </div>
        </div>
    `;
    document.body.appendChild(banner);
}

function showCookieSettings() {
    const banner = document.getElementById('cookieConsentBanner');
    if (banner) {
        banner.innerHTML = `
            <div class="cookie-content">
                <div class="cookie-text">
                    <h3>Cookie Settings</h3>
                    <p>Customize your cookie preferences below. Essential cookies cannot be disabled as they are required for the website to function properly.</p>
                    
                    <div class="cookie-options">
                        <div class="cookie-option">
                            <label class="d-flex justify-content-between align-items-center">
                                <span>
                                    <strong>Essential Cookies</strong>
                                    <small class="d-block text-muted">Required for the website to function</small>
                                </span>
                                <input type="checkbox" checked disabled>
                            </label>
                        </div>
                        
                        <div class="cookie-option">
                            <label class="d-flex justify-content-between align-items-center">
                                <span>
                                    <strong>Functional Cookies</strong>
                                    <small class="d-block text-muted">Enhance user experience and functionality</small>
                                </span>
                                <input type="checkbox" id="functionalCookies" name="functionalCookies">
                            </label>
                        </div>
                        
                        <div class="cookie-option">
                            <label class="d-flex justify-content-between align-items-center">
                                <span>
                                    <strong>Analytics Cookies</strong>
                                    <small class="d-block text-muted">Help us improve our website</small>
                                </span>
                                <input type="checkbox" id="analyticsCookies" name="analyticsCookies">
                            </label>
                        </div>
                    </div>
                </div>
                <div class="cookie-buttons">
                    <button id="saveCookieSettings" class="btn btn-primary cookie-btn">Save Settings</button>
                    <button id="acceptAllCookies" class="btn btn-outline-secondary cookie-btn">Accept All</button>
                </div>
            </div>
        `;
    }
}

function acceptAllCookies() {
    // Set cookie consent preferences to allow all cookies
    localStorage.setItem('cookieConsent', 'all');
    localStorage.setItem('functionalCookies', 'true');
    localStorage.setItem('analyticsCookies', 'true');
    hideCookieBanner();
    applyCookiePreferences();
}

function acceptEssentialCookies() {
    // Set cookie consent preferences to allow only essential cookies
    localStorage.setItem('cookieConsent', 'essential');
    localStorage.setItem('functionalCookies', 'false');
    localStorage.setItem('analyticsCookies', 'false');
    hideCookieBanner();
    applyCookiePreferences();
}

function saveCookieSettings() {
    // Save the user's cookie preferences
    const functionalCookies = document.getElementById('functionalCookies').checked;
    const analyticsCookies = document.getElementById('analyticsCookies').checked;
    
    localStorage.setItem('cookieConsent', 'custom');
    localStorage.setItem('functionalCookies', functionalCookies ? 'true' : 'false');
    localStorage.setItem('analyticsCookies', analyticsCookies ? 'true' : 'false');
    
    hideCookieBanner();
    applyCookiePreferences();
}

function hideCookieBanner() {
    const banner = document.getElementById('cookieConsentBanner');
    if (banner) {
        banner.classList.add('cookie-banner-hide');
        setTimeout(() => {
            banner.remove();
        }, 300);
    }
}

function applyCookiePreferences() {
    // Apply the cookie preferences
    // Here you would add code to respect user choices about cookies
    
    // For example, if analytics cookies are disabled, you might do something like:
    if (localStorage.getItem('analyticsCookies') !== 'true') {
        // Disable analytics tracking
        // Example: window['ga-disable-UA-XXXXX-Y'] = true;
    }
}

// Function to open cookie settings again after the banner is closed
function openCookieSettings() {
    if (document.getElementById('cookieConsentBanner')) {
        showCookieSettings();
    } else {
        showCookieBanner();
        setTimeout(showCookieSettings, 100);
    }
}