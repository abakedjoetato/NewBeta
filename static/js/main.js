/**
 * Main JavaScript for Tower of Temptation PvP Statistics Bot
 */

// Document ready function
document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Initialize popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    // Auto-dismiss alerts
    setTimeout(function() {
        const alerts = document.querySelectorAll('.alert:not(.alert-important)');
        alerts.forEach(function(alert) {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);
    
    // Handle theme toggle if present
    const themeToggleBtn = document.getElementById('theme-toggle');
    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', function() {
            document.body.classList.toggle('dark-theme');
            const isDarkTheme = document.body.classList.contains('dark-theme');
            localStorage.setItem('dark-theme', isDarkTheme);
            
            // Update icon
            const themeIcon = this.querySelector('i');
            if (isDarkTheme) {
                themeIcon.classList.remove('fa-moon');
                themeIcon.classList.add('fa-sun');
            } else {
                themeIcon.classList.remove('fa-sun');
                themeIcon.classList.add('fa-moon');
            }
        });
        
        // Check for saved theme preference
        const savedTheme = localStorage.getItem('dark-theme');
        if (savedTheme === 'true') {
            document.body.classList.add('dark-theme');
            const themeIcon = themeToggleBtn.querySelector('i');
            themeIcon.classList.remove('fa-moon');
            themeIcon.classList.add('fa-sun');
        }
    }
    
    // Add active class to nav items based on current page
    const currentPath = window.location.pathname;
    const navLinks = document.querySelectorAll('.nav-link');
    navLinks.forEach(function(link) {
        if (link.getAttribute('href') === currentPath) {
            link.classList.add('active');
        }
    });
    
    // Handle copy to clipboard functionality
    const clipboardBtns = document.querySelectorAll('.btn-copy');
    clipboardBtns.forEach(function(btn) {
        btn.addEventListener('click', function() {
            const textToCopy = this.getAttribute('data-clipboard-text');
            if (textToCopy) {
                navigator.clipboard.writeText(textToCopy).then(function() {
                    // Temporary visual feedback
                    const originalText = btn.innerHTML;
                    btn.innerHTML = '<i class="fas fa-check"></i> Copied!';
                    btn.classList.add('btn-success');
                    btn.classList.remove('btn-outline-secondary');
                    
                    setTimeout(function() {
                        btn.innerHTML = originalText;
                        btn.classList.remove('btn-success');
                        btn.classList.add('btn-outline-secondary');
                    }, 2000);
                });
            }
        });
    });
    
    // Handle table sorting if any sortable tables exist
    const sortableTables = document.querySelectorAll('.table-sortable');
    if (sortableTables.length > 0) {
        sortableTables.forEach(function(table) {
            const headers = table.querySelectorAll('th[data-sort]');
            headers.forEach(function(header) {
                header.addEventListener('click', function() {
                    const sortKey = this.getAttribute('data-sort');
                    const sortDirection = this.classList.contains('sort-asc') ? 'desc' : 'asc';
                    
                    // Remove sort classes from all headers
                    headers.forEach(h => {
                        h.classList.remove('sort-asc', 'sort-desc');
                        h.querySelector('.sort-icon')?.remove();
                    });
                    
                    // Add appropriate sort class to clicked header
                    this.classList.add('sort-' + sortDirection);
                    
                    // Add sort icon
                    const sortIcon = document.createElement('span');
                    sortIcon.classList.add('sort-icon', 'ms-1');
                    sortIcon.innerHTML = sortDirection === 'asc' 
                        ? '<i class="fas fa-sort-up"></i>' 
                        : '<i class="fas fa-sort-down"></i>';
                    this.appendChild(sortIcon);
                    
                    // Sort the table
                    sortTable(table, sortKey, sortDirection);
                });
            });
        });
    }
});

/**
 * Function to sort a table by the specified column and direction
 * @param {HTMLElement} table - The table element to sort
 * @param {string} sortKey - The key to sort by (column identifier)
 * @param {string} direction - The sort direction ('asc' or 'desc')
 */
function sortTable(table, sortKey, direction) {
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    
    // Sort the rows
    rows.sort((a, b) => {
        const aCell = a.querySelector(`td[data-sort-key="${sortKey}"]`) || a.cells[parseInt(sortKey)];
        const bCell = b.querySelector(`td[data-sort-key="${sortKey}"]`) || b.cells[parseInt(sortKey)];
        
        let aValue = aCell.getAttribute('data-sort-value') || aCell.textContent.trim();
        let bValue = bCell.getAttribute('data-sort-value') || bCell.textContent.trim();
        
        // Check if values are numbers
        const aNum = parseFloat(aValue);
        const bNum = parseFloat(bValue);
        
        if (!isNaN(aNum) && !isNaN(bNum)) {
            aValue = aNum;
            bValue = bNum;
        }
        
        // Compare values
        if (aValue < bValue) {
            return direction === 'asc' ? -1 : 1;
        } else if (aValue > bValue) {
            return direction === 'asc' ? 1 : -1;
        }
        return 0;
    });
    
    // Reorder the rows in the table
    rows.forEach(row => tbody.appendChild(row));
}

/**
 * Format a number with commas as thousands separators
 * @param {number} num - The number to format
 * @returns {string} Formatted number
 */
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

/**
 * Format a date to a relative time string (e.g., "2 hours ago")
 * @param {Date|string} date - The date to format
 * @returns {string} Formatted relative time
 */
function formatRelativeTime(date) {
    if (!(date instanceof Date)) {
        date = new Date(date);
    }
    
    const now = new Date();
    const diffInSeconds = Math.floor((now - date) / 1000);
    
    if (diffInSeconds < 60) {
        return diffInSeconds + ' seconds ago';
    }
    
    const diffInMinutes = Math.floor(diffInSeconds / 60);
    if (diffInMinutes < 60) {
        return diffInMinutes + ' minute' + (diffInMinutes > 1 ? 's' : '') + ' ago';
    }
    
    const diffInHours = Math.floor(diffInMinutes / 60);
    if (diffInHours < 24) {
        return diffInHours + ' hour' + (diffInHours > 1 ? 's' : '') + ' ago';
    }
    
    const diffInDays = Math.floor(diffInHours / 24);
    if (diffInDays < 30) {
        return diffInDays + ' day' + (diffInDays > 1 ? 's' : '') + ' ago';
    }
    
    const diffInMonths = Math.floor(diffInDays / 30);
    if (diffInMonths < 12) {
        return diffInMonths + ' month' + (diffInMonths > 1 ? 's' : '') + ' ago';
    }
    
    const diffInYears = Math.floor(diffInMonths / 12);
    return diffInYears + ' year' + (diffInYears > 1 ? 's' : '') + ' ago';
}