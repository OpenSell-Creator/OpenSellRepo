/**
 * Theme Manager - Handles light/dark theme switching
 */
class ThemeManager {
    constructor() {
        this.html = document.documentElement;
        this.initialize();
    }

    initialize() {
        // Theme is already set by the immediate script, so just update toggles
        const currentTheme = this.html.getAttribute('data-bs-theme') || 'light';
        this.updateAllThemeToggles(currentTheme);

        // Listen for system theme changes (only if no saved preference)
        this.setupSystemThemeListener();
    }

    setupSystemThemeListener() {
        if (window.matchMedia) {
            window.matchMedia('(prefers-color-scheme: dark)')
                .addEventListener('change', e => {
                    // Only change theme if user hasn't set a preference
                    try {
                        if (!localStorage.getItem('theme')) {
                            this.setTheme(e.matches ? 'dark' : 'light');
                        }
                    } catch (error) {
                        // Ignore localStorage errors
                    }
                });
        }
    }

    setTheme(theme) {
        this.html.setAttribute('data-bs-theme', theme);
        this.updateAllThemeToggles(theme);
    }

    toggleTheme() {
        const currentTheme = this.html.getAttribute('data-bs-theme');
        const newTheme = currentTheme === 'light' ? 'dark' : 'light';
        this.setTheme(newTheme);
        
        // Save preference
        try {
            localStorage.setItem('theme', newTheme);
        } catch (error) {
            // Ignore localStorage errors
        }
    }

    updateAllThemeToggles(theme) {
        // Update all theme toggle icons on the page
        document.querySelectorAll('.theme-toggle-icon').forEach(icon => {
            icon.className = `theme-toggle-icon bi ${theme === 'light' ? 'bi-moon-fill' : 'bi-sun-fill'}`;
        });
    }
}

// Immediate theme setting function (for head of document)
function setThemeImmediately() {
    const html = document.documentElement;
    
    let savedTheme = null;
    try {
        savedTheme = localStorage.getItem('theme');
    } catch (e) {}
    
    if (savedTheme && (savedTheme === 'light' || savedTheme === 'dark')) {
        html.setAttribute('data-bs-theme', savedTheme);
    } else {
        if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
            html.setAttribute('data-bs-theme', 'dark');
        } else {
            html.setAttribute('data-bs-theme', 'light');
        }
    }
}

// Initialize theme manager when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    const themeManager = new ThemeManager();
    // Make themeManager available globally for other templates
    window.themeManager = themeManager;
});

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { ThemeManager, setThemeImmediately };
}