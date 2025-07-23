document.addEventListener('DOMContentLoaded', function() {
    // Mark as read functionality
    const markReadBtn = document.getElementById('markReadBtn');
    if (markReadBtn) {
        markReadBtn.addEventListener('click', function() {
            const notificationId = this.dataset.notificationId;
            
            fetch(`{% url 'notifications:mark_read' 0 %}`.replace('0', notificationId), {
                method: 'POST',
                headers: {
                    'X-CSRFToken': '{{ csrf_token }}',
                    'Content-Type': 'application/json'
                },
                credentials: 'same-origin'
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    // Remove unread indicator
                    const unreadDot = document.querySelector('.unread-dot');
                    if (unreadDot) {
                        unreadDot.remove();
                    }
                    
                    // Hide mark read button
                    this.style.display = 'none';
                    
                    // Show success feedback
                    showToast('Notification marked as read', 'success');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showToast('Failed to mark as read', 'error');
            });
        });
    }
    
    // Simple toast function
    function showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `alert alert-${type === 'success' ? 'success' : 'danger'} position-fixed`;
        toast.style.cssText = 'top: 20px; right: 20px; z-index: 1050; min-width: 300px;';
        toast.innerHTML = `
            <div class="d-flex align-items-center">
                <span>${message}</span>
                <button type="button" class="btn-close ms-auto" onclick="this.parentElement.parentElement.remove()"></button>
            </div>
        `;
        document.body.appendChild(toast);
        
        setTimeout(() => {
            if (toast.parentElement) {
                toast.remove();
            }
        }, 3000);
    }
});