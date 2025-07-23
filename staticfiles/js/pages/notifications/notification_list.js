document.addEventListener('DOMContentLoaded', function() {
    // Mark individual notification as read
    document.querySelectorAll('.mark-read-btn').forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            const notificationId = this.dataset.notificationId;
            const notificationItem = this.closest('.notification-item');
            
            markNotificationAsRead(notificationId, notificationItem);
        });
    });

    // Mark all as read
    const markAllBtn = document.getElementById('markAllReadBtn');
    if (markAllBtn) {
        markAllBtn.addEventListener('click', function() {
            if (!confirm('Mark all notifications as read?')) return;
            
            fetch('{% url "notifications:mark_all_read" %}', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': '{{ csrf_token }}',
                    'Content-Type': 'application/json'
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    // Update UI
                    document.querySelectorAll('.unread-indicator').forEach(el => el.remove());
                    document.querySelectorAll('.new-indicator').forEach(el => el.remove());
                    document.querySelectorAll('.mark-read-btn').forEach(el => el.remove());
                    
                    const countEl = document.querySelector('.notification-count');
                    if (countEl) countEl.textContent = '0';
                    
                    showToast('All notifications marked as read', 'success');
                }
            })
            .catch(() => showToast('Failed to mark all as read', 'error'));
        });
    }

    // Clear all notifications
    const clearAllBtn = document.getElementById('clearAllBtn');
    if (clearAllBtn) {
        clearAllBtn.addEventListener('click', function() {
            if (!confirm('Delete all notifications? This cannot be undone.')) return;
            
            fetch('{% url "notifications:clear_all" %}', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': '{{ csrf_token }}',
                    'Content-Type': 'application/json'
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    location.reload();
                }
            })
            .catch(() => showToast('Failed to clear notifications', 'error'));
        });
    }

    // Category filtering
    document.querySelectorAll('.filter-btn').forEach(button => {
        button.addEventListener('click', function() {
            const category = this.dataset.category;
            
            // Update active state
            document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
            this.classList.add('active');
            
            // Filter notifications
            document.querySelectorAll('.notification-item').forEach(item => {
                const shouldShow = category === 'all' || item.dataset.category === category;
                item.style.display = shouldShow ? 'block' : 'none';
            });
        });
    });

    function markNotificationAsRead(notificationId, notificationElement) {
        fetch(`{% url 'notifications:mark_read' 0 %}`.replace('0', notificationId), {
            method: 'POST',
            headers: {
                'X-CSRFToken': '{{ csrf_token }}',
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                // Update UI
                notificationElement.querySelector('.unread-indicator')?.remove();
                notificationElement.querySelector('.new-indicator')?.remove();
                notificationElement.querySelector('.mark-read-btn')?.remove();
                
                showToast('Marked as read', 'success');
            }
        })
        .catch(() => showToast('Failed to mark as read', 'error'));
    }

    function showToast(message, type) {
        const toast = document.createElement('div');
        toast.className = `alert alert-${type === 'success' ? 'success' : 'danger'} position-fixed`;
        toast.style.cssText = 'top: 20px; right: 20px; z-index: 1060; min-width: 280px;';
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