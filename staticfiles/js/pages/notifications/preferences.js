document.addEventListener('DOMContentLoaded', function() {
    // Handle frequency radio button clicks
    document.querySelectorAll('.frequency-item').forEach(item => {
        item.addEventListener('click', function() {
            const radio = this.querySelector('input[type="radio"]');
            if (radio) {
                radio.checked = true;
            }
        });
    });

    // Reset to defaults function
    window.resetToDefaults = function() {
        if (!confirm('Reset all preferences to their default values?')) return;
        
        // Check all checkboxes (default is true for most)
        document.querySelectorAll('.preference-toggle').forEach(toggle => {
            toggle.checked = true;
        });
        
        // Set frequency to instant
        document.getElementById('freq_instant').checked = true;
        
        showToast('Preferences reset to defaults', 'info');
    };

    // Form submission feedback
    const form = document.querySelector('.preferences-form');
    if (form) {
        form.addEventListener('submit', function() {
            showToast('Preferences saved successfully!', 'success');
        });
    }

    // Live preview of changes
    document.querySelectorAll('.preference-toggle, input[name="frequency"]').forEach(input => {
        input.addEventListener('change', function() {
            // Visual feedback for immediate changes
            const item = this.closest('.preference-item, .frequency-item');
            if (item) {
                item.style.transform = 'scale(0.98)';
                setTimeout(() => {
                    item.style.transform = 'scale(1)';
                }, 150);
            }
        });
    });

    function showToast(message, type) {
        const toast = document.createElement('div');
        toast.className = `alert alert-${type === 'success' ? 'success' : type === 'info' ? 'info' : 'primary'} position-fixed`;
        toast.style.cssText = 'top: 20px; right: 20px; z-index: 1060; min-width: 300px;';
        toast.innerHTML = `
            <div class="d-flex align-items-center">
                <span>${message}</span>
                <button type="button" class="btn-close ms-auto" onclick="this.parentElement.parentElement.remove()"></button>
            </div>
        `;
        document.body.appendChild(toast);
        
        setTimeout(() => toast.remove(), 3000);
    }
});